#!/usr/bin/env python3
"""
Core RAMP-UA model.

Created on Tue Apr 6

@author: Anna on Nick's code, for the national scaling-up
"""
import sys
import multiprocessing
import pandas as pd
import numpy as np

pd.set_option(
    "display.expand_frame_repr", False
)  # Don't wrap lines when displaying DataFrames
import os
import click
import pickle
from yaml import load, SafeLoader
from shutil import copyfile

from ramp.run import run_opencl
from ramp.snapshot_convertor import SnapshotConvertor
from ramp.snapshot import Snapshot
from ramp.params import Params, IndividualHazardMultipliers, LocationHazardMultipliers
from ramp.initialisation_cache import InitialisationCache
from ramp.constants import Constants
from ramp.constants import ColumnNames


@click.command()
@click.option(
    "-p",
    "--parameters-file",
    type=click.Path(exists=True),
    help="Parameters file to use to configure the model. This must be located in the working directory.",
)
def main(parameters_file):
    """
    Main function which runs the population initialisation, then chooses which model to run, either the Python/R
    model or the OpenCL model
    """

    print(f"--\nReading parameters file: {parameters_file}\n--")

    try:
        with open(parameters_file, "r") as f:
            parameters = load(f, Loader=SafeLoader)
            sim_params = parameters[
                "microsim"
            ]  # Parameters for the dynamic microsim (python)
            calibration_params = parameters["microsim_calibration"]
            disease_params = parameters[
                "disease"
            ]  # Parameters for the disease model (r)
            # Utility parameters
            scenario = sim_params["scenario"]
            initialise = sim_params["initialise"]
            iterations = sim_params["iterations"]
            study_area = sim_params["study-area"]
            output = sim_params["output"]
            output_every_iteration = sim_params["output-every-iteration"]
            debug = sim_params["debug"]
            repetitions = sim_params["repetitions"]
            use_lockdown = sim_params["use-lockdown"]
            open_cl_model = sim_params["opencl-model"]
            opencl_gui = sim_params["opencl-gui"]
            opencl_gpu = sim_params["opencl-gpu"]
            startDate = sim_params["start-date"]
    except Exception as error:
        print("Error in parameters file format")
        raise error

    # Check the parameters are sensible
    if iterations < 1:
        raise ValueError(
            "Iterations must be > 1. If you want to just initialise the model and then exit,"
            "set initialise : true"
        )
    if repetitions < 1:
        raise ValueError("Repetitions must be greater than 0")
    if (not output) and output_every_iteration:
        raise ValueError(
            "Can't choose to not output any data (output=False) but also write the data at every "
            "iteration (output_every_iteration=True)"
        )

    if not os.path.exists(
        os.path.join(Constants.Paths.PROCESSED_DATA.FULL_PATH_FOLDER)
    ):
        raise Exception(
            "Data folder structure not valid. Make sure you are running within correct working directory."
        )

    # Accessing the cache data (pre-processed data) generated by the module main_initialisation.
    # This is located in the selected study area folder in processed_data
    # The study area is assigned in model_parameters/default.yml in the class "microsim.study-area"
    study_area_folder_in_processed_data = os.path.join(
        Constants.Paths.PROCESSED_DATA.FULL_PATH_FOLDER, study_area
    )  # this generates the folder name
    print(f"study area folder {study_area_folder_in_processed_data}")
    if not os.path.exists(study_area_folder_in_processed_data):
        raise Exception(
            "Study area folder doesn't exist, check the spelling or the location"
        )

    run_opencl_model(
        iterations,
        study_area,
        opencl_gui,
        opencl_gpu,
        initialise,
        calibration_params,
        disease_params,
        parameters_file,
        use_lockdown,
    )


def run_opencl_model(
    iterations,
    # regional_data_dir_full_path,
    study_area,
    use_gui,
    use_gpu,
    initialise,
    calibration_params,
    disease_params,
    parameters_file,
    use_lockdown,
):
    study_area_folder_in_processed_data = os.path.join(
        Constants.Paths.PROCESSED_DATA.FULL_PATH_FOLDER, study_area
    )
    snapshot_cache_filepath = os.path.join(
        study_area_folder_in_processed_data, "snapshot", "cache.npz"
    )

    # Choose whether to load snapshot file from cache, or create a snapshot from population data
    if not os.path.exists(snapshot_cache_filepath):
        print("\nGenerating Snapshot for OpenCL model")
        cache = InitialisationCache(cache_dir=study_area_folder_in_processed_data)
        if cache.is_empty():
            raise Exception(
                f"You will need to run the main_initialisation module because the cache is empty"
            )
        print("Loading data from previous cache")
        individuals, activity_locations, lockdown_file = cache.read_from_cache()

        if use_lockdown:
            print(f"Loading the lockdown scenario")
            time_activity_multiplier = lockdown_file.change
            time_activity_multiplier = time_activity_multiplier[
                startDate : len(time_activity_multiplier)
            ]  # offset file to start date
            time_activity_multiplier.index = range(len(time_activity_multiplier))
        else:
            time_activity_multiplier = np.ones(2000)

        snapshot_converter = SnapshotConvertor(
            individuals,
            activity_locations,
            time_activity_multiplier,
            study_area_folder_in_processed_data,
        )
        snapshot = snapshot_converter.generate_snapshot()
        if not os.path.exists(
            os.path.join(study_area_folder_in_processed_data, "snapshot")
        ):
            os.makedirs(os.path.join(study_area_folder_in_processed_data, "snapshot"))
        snapshot.save(
            snapshot_cache_filepath
        )  # store snapshot in cache so we can load later
    else:  # load cached snapshot
        snapshot = Snapshot.load_full_snapshot(path=snapshot_cache_filepath)

    # set the random seed of the model
    snapshot.seed_prngs(42)

    # set params
    if calibration_params is not None and disease_params is not None:
        snapshot.update_params(create_params(calibration_params, disease_params))

        if disease_params["improve_health"]:
            print("Switching to healthier population")
            snapshot.switch_to_healthier_population()
    if initialise:
        print(
            "Have finished initialising model. -init flag is set so not running it. Exiting"
        )
        return

    run_mode = "GUI" if use_gui else "headless"
    print(f"\nRunning OpenCL model in {run_mode} mode")
    run_opencl(
        snapshot, study_area, parameters_file, iterations, use_gui, use_gpu, quiet=False
    )


def create_params(calibration_params, disease_params):
    current_risk_beta = disease_params["current_risk_beta"]

    # NB: OpenCL model incorporates the current risk beta by pre-multiplying the hazard multipliers with it
    location_hazard_multipliers = LocationHazardMultipliers(
        retail=calibration_params["hazard_location_multipliers"]["Retail"]
        * current_risk_beta,
        nightclubs=calibration_params["hazard_location_multipliers"]["Nightclubs"]
        * current_risk_beta,
        primary_school=calibration_params["hazard_location_multipliers"][
            "PrimarySchool"
        ]
        * current_risk_beta,
        secondary_school=calibration_params["hazard_location_multipliers"][
            "SecondarySchool"
        ]
        * current_risk_beta,
        home=calibration_params["hazard_location_multipliers"]["Home"]
        * current_risk_beta,
        work=calibration_params["hazard_location_multipliers"]["Work"]
        * current_risk_beta,
    )

    individual_hazard_multipliers = IndividualHazardMultipliers(
        presymptomatic=calibration_params["hazard_individual_multipliers"][
            "presymptomatic"
        ],
        asymptomatic=calibration_params["hazard_individual_multipliers"][
            "asymptomatic"
        ],
        symptomatic=calibration_params["hazard_individual_multipliers"]["symptomatic"],
    )

    obesity_multipliers = [
        disease_params["overweight"],
        disease_params["obesity_30"],
        disease_params["obesity_35"],
        disease_params["obesity_40"],
    ]

    return Params(
        location_hazard_multipliers=location_hazard_multipliers,
        individual_hazard_multipliers=individual_hazard_multipliers,
        obesity_multipliers=obesity_multipliers,
        cvd_multiplier=disease_params["cvd"],
        diabetes_multiplier=disease_params["diabetes"],
        bloodpressure_multiplier=disease_params["bloodpressure"],
    )


if __name__ == "__main__":
    main()

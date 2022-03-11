import os
print(f"*** check 1 \n {os.getcwd()}")
print(f"*** check 2 \n {os.path.dirname(__file__)}")
# not needed anymore: # os.chdir(os.path.dirname(__file__)) # change dir to the current file's path
print(f"*** check 3 \n {os.getcwd()}")

abspath = "/Users/fbenitez/Documents/ResearchATI/EcoTwins_Rust/rampfs/"
#code_folder = "coding"
#initialise_folder = "initialise"
#model_folder = "model"
#r_python_model_folder = "microsim"
#opencl_model_folder = "opencl"
opencl_source_folder = "ramp"
opencl_fonts_folder = "fonts"
opencl_kernels_folder = "kernels"
opencl_shaders_folder = "shaders"

class OPENCL_SOURCE:
    SOURCE_FOLDER = opencl_source_folder
    FULL_PATH_SOURCE = os.path.join(abspath,SOURCE_FOLDER)
    KERNELS_FOLDER = opencl_kernels_folder
    FULL_PATH_KERNEL_FOLDER = os.path.join(abspath,SOURCE_FOLDER,KERNELS_FOLDER)
            # **** IMPORTANT ****
            # The following variable is used only by Simulator module
            # OpenCL kernels are really sensible to the path provided
            # Specifically, you have to start from 'after' the current working directory
            # that currently is abspath/project_folder/ (must be consistent with the  configurations)
            
    FOLDER_PATH_FOR_KERNEL = os.path.join(SOURCE_FOLDER, KERNELS_FOLDER)
    KERNEL_FILE = "ramp_ua.cl"
    FULL_PATH_KERNEL_FILE = os.path.join(abspath,SOURCE_FOLDER,KERNELS_FOLDER,KERNEL_FILE)
            # **** END ****
    SHADERS_FOLDER = opencl_shaders_folder
    FULL_PATH_SHADERS_FOLDER = os.path.join(abspath,SOURCE_FOLDER,SHADERS_FOLDER)
            # The following variable is used only by shader.py
            # OpenCL kernels are really sensible to the path provided
            # Specifically, you have to start from the current working directory
            # that currently is abspath/project_folder/coding/ (see configurations)
    FOLDER_PATH_FOR_SHADERS = os.path.join(SOURCE_FOLDER,SHADERS_FOLDER)
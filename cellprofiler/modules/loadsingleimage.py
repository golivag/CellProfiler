"""<b>Load Single Image</b> loads a single image for use in all image cycles
<hr>

<p>This module tells CellProfiler where to retrieve a single image and gives the image a
meaningful name by which the other modules can access it. The module 
executes only the first time through the pipeline; thereafter the image
is accessible to all subsequent processing cycles. This is
particularly useful for loading an image like an illumination correction
image for use by the <b>CorrectIlluminationApply</b> module, when that single
image will be used to correct all images in the analysis run.</p>

<h3>Technical note</h3>

For most purposes, you will probably want to use the <b>LoadImages</b> module, not 
<b>LoadSingleImage</b>. The reason is that <b>LoadSingleImage</b> does not actually 
create image sets (or even a single image set). Instead, it adds the single image 
to every image cycle for an <i>already existing</i> image set. Hence 
<b>LoadSingleImage</b> should never be used as the only image-loading module in a 
pipeline; attempting to do so will display a warning message in the module settings. 
<p>If you have a single file to load in the pipeline (and only that file), you 
will want to use <b>LoadImages</b> or <b>LoadData</b> with a single, hardcoded file name. 

See also <b>LoadImages</b>,<b>LoadData</b>.

"""
__version__="$Revision$"

# CellProfiler is distributed under the GNU General Public License.
# See the accompanying file LICENSE for details.
# 
# Developed by the Broad Institute
# Copyright 2003-2010
# 
# Please see the AUTHORS file for credits.
# 
# Website: http://www.cellprofiler.org

import hashlib
import numpy as np
import re
import os

import cellprofiler.objects as cpo
import cellprofiler.cpimage as cpi
import cellprofiler.cpmodule as cpm
import cellprofiler.measurements as cpmeas
import cellprofiler.preferences as cpprefs
import cellprofiler.settings as cps
from loadimages import LoadImagesImageProvider
from loadimages import C_SCALING, C_FILE_NAME, C_PATH_NAME, C_MD5_DIGEST, C_OBJECTS_FILE_NAME, C_OBJECTS_PATH_NAME
from loadimages import convert_image_to_objects
from loadimages import IO_IMAGES, IO_OBJECTS, IO_ALL
import identify as I
from cellprofiler.gui.help import USING_METADATA_TAGS_REF, USING_METADATA_HELP_REF
from cellprofiler.preferences import standardize_default_folder_names, \
     DEFAULT_INPUT_FOLDER_NAME, DEFAULT_OUTPUT_FOLDER_NAME, \
     IO_FOLDER_CHOICE_HELP_TEXT, IO_WITH_METADATA_HELP_TEXT

DIR_CUSTOM_FOLDER = "Custom folder"
DIR_CUSTOM_WITH_METADATA = "Custom with metadata"

FILE_TEXT = "Filename of the image to load (Include the extension, e.g., .tif)"
URL_TEXT = "URL of the image to load (Include the extension, e.g., .tif)"

S_FILE_SETTINGS_COUNT_V4 = 3
S_FILE_SETTINGS_COUNT_V5 = 5

class LoadSingleImage(cpm.CPModule):

    module_name = "LoadSingleImage"
    category = "File Processing"
    variable_revision_number = 5
    def create_settings(self):
        """Create the settings during initialization
        
        """
        self.directory = cps.DirectoryPath(
            "Input image file location", support_urls = True,
            doc = '''Select the folder containing the image(s) to be loaded. Generally, 
            it is best to store the image you want to load in either the Default Input or 
            Output Folder, so that the correct image is loaded into the pipeline 
            and typos are avoided. %(IO_FOLDER_CHOICE_HELP_TEXT)s
            
            <p>%(IO_WITH_METADATA_HELP_TEXT)s %(USING_METADATA_TAGS_REF)s For instance, 
            if you have a "Plate" metadata tag, and your single files are 
            organized in subfolders named with the "Plate" tag, you can select one of the 
            subfolder options and then specify a subfolder name of "\g&lt;Plate&gt;" 
            to get the files from the subfolder associated with that image's plate. The module will 
            substitute the metadata values for the current image set for any metadata tags in the 
            folder name. %(USING_METADATA_HELP_REF)s.</p>'''%globals())
        
        self.file_settings = []
        self.add_file(can_remove = False)
        self.add_button = cps.DoSomething("", "Add another image", self.add_file)

    def add_file(self, can_remove = True):
        """Add settings for another file to the list"""
        group = cps.SettingsGroup()
        if can_remove:
            group.append("divider", cps.Divider(line=False))
        def get_directory_fn():
            return self.directory.get_absolute_path()
        
        group.append("file_name", cps.FilenameText(
            FILE_TEXT,
            "None",
            metadata=True,
            get_directory_fn = get_directory_fn,
            exts = [("Tagged image file (*.tif)","*.tif"),
                    ("Portable network graphics (*.png)", "*.png"),
                    ("JPEG file (*.jpg)", "*.jpg"),
                    ("Bitmap file (*.bmp)", "*.bmp"),
                    ("GIF file (*.gif)", "*.gif"),
                    ("Matlab image (*.mat)","*.mat"),
                    ("All files (*.*)", "*.*")],doc = """
                    The filename can be constructed in one of two ways:
                    <ul>
                    <li>As a fixed filename (e.g., <i>Exp1_D03f00d0.tif</i>). 
                    <li>Using the metadata associated with an image set in 
                    <b>LoadImages</b> or <b>LoadData</b>. This is especially useful 
                    if you want your output given a unique label according to the
                    metadata corresponding to an image group. The name of the metadata 
                    to substitute is included in a special tag format embedded 
                    in your file specification. %(USING_METADATA_TAGS_REF)s%(USING_METADATA_HELP_REF)s.</li>
                    </ul>
                    <p>Keep in mind that in either case, the image file extension, if any, must be included."""% globals() ))
        
        group.append("image_object_choice", cps.Choice(
                    'Load as images or objects?', IO_ALL,
                    doc = """
                    This setting determines whether you load an image as image data
                    or as segmentation results (i.e., objects):
                    <ul>
                    <li><i>Images:</i> The input image will be given a user-specified name by
                    which it will be refered downstream. This is the most common usage for this
                    module.</li>
                    <li><i>Objects:</i> Use this option if the input image is a label matrix 
                    and you want to obtain the objects that it defines. A <i>label matrix</i>
                    is a grayscale or color image in which the connected regions share the
                    same label, and defines how objects are represented in CellProfiler.
                    The labels are integer values greater than or equal to 0. 
                    The elements equal to 0 are the background, whereas the elements equal to 1 
                    make up one object, the elements equal to 2 make up a second object, and so on.
                    This option allows you to use the objects without needing to insert an 
                    <b>Identify</b> module to extract them first. See <b>IdentifyPrimaryObjects</b> 
                    for more details.</li>
                    </ul>"""))
        
        group.append("image_name", cps.FileImageNameProvider("Name the image that will be loaded", 
                    "OrigBlue", doc = '''
                    <i>(Used only if an image is output)</i><br>
                    What do you want to call the image you are loading? 
                    You can use this name to select the image in downstream modules.'''))
        
        group.append("rescale", cps.Binary(
                    "Rescale intensities?",True,
                    doc = """
                    <i>(Used only if an image is output)</i><br>
                    This option determines whether image metadata should be
                    used to rescale the image's intensities. Some image formats
                    save the maximum possible intensity value along with the pixel data.
                    For instance, a microscope might acquire images using a 12-bit
                    A/D converter which outputs intensity values between zero and 4095,
                    but stores the values in a field that can take values up to 65535.
                    Check this setting to rescale the image intensity so that
                    saturated values are rescaled to 1.0 by dividing all pixels
                    in the image by the maximum possible intensity value. Uncheck this 
                    setting to ignore the image metadata and rescale the image
                    to 0 - 1.0 by dividing by 255 or 65535, depending on the number
                    of bits used to store the image."""))

        group.append("object_name", cps.ObjectNameProvider(
                    'Name this loaded object',
                    "Nuclei",
                    doc = """<i>(Used only if objects are output)</i><br>
                    This is the name for the objects loaded from your image"""))
        
        if can_remove:
            group.append("remove", cps.RemoveSettingButton("", "Remove this image", self.file_settings, group))
        self.file_settings.append(group)

    def settings(self):
        """Return the settings in the order in which they appear in a pipeline file"""
        result = [self.directory]
        for file_setting in self.file_settings:
            url_based = (self.directory.dir_choice == cps.URL_FOLDER_NAME)
            file_setting.file_name.set_browsable(not url_based)
            file_setting.file_name.text = URL_TEXT if url_based else FILE_TEXT
            result += [file_setting.file_name, 
                        file_setting.image_object_choice,
                        file_setting.image_name,
                        file_setting.rescale, 
                        file_setting.object_name]
        return result
    
    def help_settings(self):
        result = [self.directory]
        image_group = self.file_settings[0]
        result += [image_group.file_name, 
                    image_group.image_object_choice,
                    image_group.image_name,
                    image_group.rescale, 
                    image_group.object_name]
        return result
    
    def visible_settings(self):
        result = [self.directory]
        for file_setting in self.file_settings:
            result += [file_setting.file_name,
                       file_setting.image_object_choice]
            if self.file_wants_images(file_setting):
                result += [file_setting.image_name,
                            file_setting.rescale]
            else:
                result += [file_setting.object_name]
        result.append(self.add_button)
        return result 

    def prepare_settings(self, setting_values):
        """Adjust the file_settings depending on how many files there are"""
        count = (len(setting_values)-1) / S_FILE_SETTINGS_COUNT_V5
        del self.file_settings[count:]
        while len(self.file_settings) < count:
            self.add_file()

    def prepare_to_create_batch(self, pipeline, image_set_list, fn_alter_path):
        '''Prepare to create a batch file
        
        This function is called when CellProfiler is about to create a
        file for batch processing. It will pickle the image set list's
        "legacy_fields" dictionary. This callback lets a module prepare for
        saving.
        
        pipeline - the pipeline to be saved
        image_set_list - the image set list to be saved
        fn_alter_path - this is a function that takes a pathname on the local
                        host and returns a pathname on the remote host. It
                        handles issues such as replacing backslashes and
                        mapping mountpoints. It should be called for every
                        pathname stored in the settings or legacy fields.
        '''
        self.directory.alter_for_create_batch_files(fn_alter_path)
        return True

    def get_base_directory(self, workspace):
        return self.directory.get_absolute_path(workspace.measurements)
    
    def get_file_names(self, workspace):
        """Get the files for the current image set
        
        workspace - workspace for current image set
        
        returns a dictionary of image_name keys and file path values
        """
        result = {}
        for file_setting in self.file_settings:
            file_pattern = file_setting.file_name.value
            file_name = workspace.measurements.apply_metadata(file_pattern)
            result[file_setting.image_name.value] = file_name
                
        return result
    
    def get_file_settings(self, image_name):
        '''Get the file settings associated with a given image name'''
        for file_setting in self.file_settings:
            if file_setting.image_name == image_name:
                return file_setting
        return None
            
    
    def file_wants_images(self, file_setting):
        '''True if the file_setting produces images, false if it produces objects'''
        return file_setting.image_object_choice == IO_IMAGES
    
    def run(self, workspace):
        dict = self.get_file_names(workspace)
        root = self.get_base_directory(workspace)
        statistics = [("Image name","File")]
        m = workspace.measurements
        for image_name in dict.keys():
            file_settings = self.get_file_settings(image_name)
            wants_images = self.file_wants_images(file_settings)
            provider = LoadImagesImageProvider(
                image_name, root, dict[image_name], file_settings.rescale.value)
            workspace.image_set.providers.append(provider)
            image = provider.provide_image(workspace.image_set)
            pixel_data = image.pixel_data
            statistics += [(image_name, dict[image_name])]
            #
            # Add measurements
            #
            if wants_images:
                m.add_measurement('Image',C_FILE_NAME + '_'+image_name, dict[image_name])
                m.add_measurement('Image',C_PATH_NAME + '_'+image_name, root)
                digest = hashlib.md5()
                digest.update(np.ascontiguousarray(pixel_data).data)
                m.add_measurement('Image',C_MD5_DIGEST + '_'+image_name, 
                                  digest.hexdigest())
                m.add_image_measurement('_'.join((C_SCALING, image_name)),
                                        image.scale)
            else:
                #
                # Save as objects.
                #
                path_name_category = C_OBJECTS_PATH_NAME
                file_name_category = C_OBJECTS_FILE_NAME
                pixel_data = convert_image_to_objects(pixel_data)
                o = cpo.Objects()
                o.segmented = pixel_data
                object_set = workspace.object_set
                assert isinstance(object_set, cpo.ObjectSet)
                object_name = file_settings.object_name.value
                object_set.add_objects(o, object_name)
                provider.release_memory()
                I.add_object_count_measurements(m, object_name, o.count)
                I.add_object_location_measurements(m, object_name, pixel_data)
        if workspace.frame:
            title = "Load single image: image cycle # %d"%(workspace.measurements.image_set_number+1)
            figure = workspace.create_or_find_figure(title="LoadSingleImage, image cycle #%d"%(
                workspace.measurements.image_set_number),
                                                     subplots=(1,1))
            figure.subplot_table(0,0, statistics)
    
    def get_measurement_columns(self, pipeline):
        columns = []
        for file_setting in self.file_settings:
            if not self.file_wants_images(file_setting):
                name = file_setting.object_name.value
                columns += I.get_object_measurement_columns(name)
                path_name_category = C_OBJECTS_PATH_NAME
                file_name_category = C_OBJECTS_FILE_NAME
            else:
                name = file_setting.image_name.value
                path_name_category = C_PATH_NAME
                file_name_category = C_FILE_NAME
                columns += [(cpmeas.IMAGE, "_".join((C_MD5_DIGEST, name)), 
                              cpmeas.COLTYPE_VARCHAR_FORMAT%32)]
                columns += [(cpmeas.IMAGE, "_".join((C_SCALING, name)),
                              cpmeas.COLTYPE_FLOAT)]
                
            columns += [(cpmeas.IMAGE, "_".join((file_name_category, name)), 
                              cpmeas.COLTYPE_VARCHAR_FILE_NAME)]
            columns += [(cpmeas.IMAGE, "_".join((path_name_category, name)), 
                              cpmeas.COLTYPE_VARCHAR_PATH_NAME)]
            
        return columns
    
    def get_categories(self, pipeline, object_name):
        object_names = sum(
            [[file_setting.object_name.value for file_setting in self.file_settings if file_setting.image_object_choice == IO_OBJECTS ]], [])
        has_image_name = any(
            [ True for file_setting in self.file_settings if file_setting.image_object_choice == IO_IMAGES])
        res = []
        if object_name == cpmeas.IMAGE:
            if has_image_name:
                res += [C_FILE_NAME, C_MD5_DIGEST, C_PATH_NAME, C_SCALING]
            if len(object_names) > 0:
                res += [C_OBJECTS_FILE_NAME, C_OBJECTS_PATH_NAME, I.C_COUNT]
        elif object_name in object_names:
            res += [I.C_LOCATION, I.C_NUMBER]
        return res
    
    def get_measurements(self, pipeline, object_name, category):
        '''Return the measurements that this module produces
        
        object_name - return measurements made on this object (or 'Image' for image measurements)
        category - return measurements made in this category
        '''
        result = []
        object_names = sum(
            [[file_setting.object_name.value for file_setting in self.file_settings if file_setting.image_object_choice == IO_OBJECTS ]], [])
        
        if object_name == cpmeas.IMAGE:
            if category == I.C_COUNT:
                result += object_names
            else:
                result += [c[1].split('_',1)[1] 
                           for c in self.get_measurement_columns(pipeline)
                           if c[1].split('_')[0] == category]
        elif object_name in object_names:
            if category == I.C_NUMBER:
                result += [I.FTR_OBJECT_NUMBER]
            elif category == I.C_LOCATION:
                result += [I.FTR_CENTER_X, I.FTR_CENTER_Y]
        return result
    
    def validate_module(self, pipeline):
        '''Keep users from using LoadSingleImage to define image sets'''
        if not any([x.is_load_module() for x in pipeline.modules()]):
            raise cps.ValidationError(
                "LoadSingleImage cannot be used to run a pipeline on one "
                "image file. Please use LoadImages or LoadData instead.",
                self.directory)
        
    def upgrade_settings(self, setting_values, variable_revision_number, module_name, from_matlab):
        if from_matlab and variable_revision_number == 4:
            new_setting_values = list(setting_values)
            # The first setting was blank in Matlab. Now it contains
            # the directory choice
            if setting_values[1] == '.':
                new_setting_values[0] = cps.DEFAULT_INPUT_FOLDER_NAME
            elif setting_values[1] == '&':
                new_setting_values[0] = cps.DEFAULT_OUTPUT_FOLDER_NAME
            else:
                new_setting_values[0] = DIR_CUSTOM_FOLDER
            #
            # Remove "Do not use" images
            #
            for i in [8, 6, 4]:
                if new_setting_values[i+1] == cps.DO_NOT_USE:
                    del new_setting_values[i:i+2]
            setting_values = new_setting_values
            from_matlab = False
            variable_revision_number = 1
        #
        # Minor revision: default image folder -> default input folder
        #
        if variable_revision_number == 1 and not from_matlab:
            if setting_values[0].startswith("Default image"):
                dir_choice = cps.DEFAULT_INPUT_FOLDER_NAME
                custom_directory = setting_values[1]
            elif setting_values[0] in (DIR_CUSTOM_FOLDER, DIR_CUSTOM_WITH_METADATA):
                custom_directory = setting_values[1]
                if custom_directory[0] == ".":
                    dir_choice = cps.DEFAULT_INPUT_SUBFOLDER_NAME
                elif custom_directory[0] == "&":
                    dir_choice = cps.DEFAULT_OUTPUT_SUBFOLDER_NAME
                    custom_directory = "."+custom_directory[1:]
                else:
                    dir_choice = cps.ABSOLUTE_FOLDER_NAME
            else:
                dir_choice = setting_values[0]
                custom_directory = setting_values[1]
            directory = cps.DirectoryPath.static_join_string(
                dir_choice, custom_directory)
            setting_values = [directory] + setting_values[2:]
            variable_revision_number = 2
                
        # Standardize input/output directory name references
        SLOT_DIR = 0
        setting_values[SLOT_DIR] = cps.DirectoryPath.upgrade_setting(
            setting_values[SLOT_DIR])
        
        # changes to DirectoryPath and URL handling
        if variable_revision_number == 2 and (not from_matlab):
            dir = setting_values[0]
            dir_choice, custom_dir = cps.DirectoryPath.split_string(dir)
            if dir_choice == cps.URL_FOLDER_NAME:
                dir = cps.DirectoryPath.static_join_string(dir_choice, '')
                filenames = setting_values[1::2]
                imagenames = setting_values[2::2]
                setting_values = [dir] + zip([custom_dir + '/' + filename for filename in filenames],
                                             imagenames)
            variable_revision_number = 3
            
        if variable_revision_number == 3 and (not from_matlab):
            # Added rescale option
            new_setting_values = setting_values[:1]
            for i in range(1, len(setting_values), 2):
                new_setting_values += setting_values[i:(i+2)] + [cps.YES]
            setting_values = new_setting_values
            variable_revision_number = 4

        if variable_revision_number == 4 and (not from_matlab):
            # Added object loading option
            new_setting_values = setting_values[:1]
            for i in range(1, len(setting_values), S_FILE_SETTINGS_COUNT_V4):
                new_setting_values += [setting_values[i]] + \
                                        [IO_IMAGES] + \
                                        setting_values[(i+1):(i+S_FILE_SETTINGS_COUNT_V4)] + \
                                        ["Nuclei"]
            setting_values = new_setting_values
            variable_revision_number = 5
            
        return setting_values, variable_revision_number, from_matlab


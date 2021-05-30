import os
import glob
import shutil
import uuid

from gi.repository import GObject, Gtk, Gdk

from zim.plugins import PluginClass
from zim.gui.mainwindow import MainWindowExtension
from zim.gui.widgets import Dialog, ErrorDialog
from zim.actions import action
from zim.applications import Application, ApplicationError
from zim.fs import File, TmpFile

# from zim.fs import TmpFile

xournalppcmd = "xournalpp"
imagemagickcmd = ("convert", "version")


class XournalppPlugin(PluginClass):
    plugin_info = {
        "name": _("Xournalpp Drawing"),
        "description": _(
            "This integrates xournalpp with zim to enable importing scribbled notes as resizable transparent .png images"
        ),
        "author": "introt, VivekThazhathattil",
    }

    plugin_preferences = (
        # key, type, label, default
        ("xopp_dir", "string", _("Xopp Directory"), "~"),
        ("template_file", "string", _("Xournalpp template file path"), ""),
        ("clean_xopp_dir", "bool", _("Clean Xopp directory after use"), False),
    )

    @classmethod
    def check_dependencies(klass):
        has_xournalpp = Application(xournalppcmd).tryexec()
        has_imagemagick = Application(imagemagickcmd).tryexec()
        return (has_xournalpp and has_imagemagick), [
            ("xournalpp", has_xournalpp, True),
            ("imagemagick", has_imagemagick, True),
        ]


class XournalppMainWindowExtension(MainWindowExtension):
    def __init__(self, plugin, window):
        super().__init__(plugin, window)
        self.xopp_dir = self.plugin.preferences["xopp_dir"]
        self.template_file = self.plugin.preferences["template_file"]
        self.clean_dir_pref = self.plugin.preferences["clean_xopp_dir"]
        self.template_valid = False  # by default use the manual saving option
        self.xournalpp = None
        self.imagemagick = None

    def is_xopp_dir_valid(self):
        full_path = os.path.expanduser(self.xopp_dir)
        return os.path.isdir(full_path)

    def is_template_file_valid(self):
        full_path = ""
        if self.template_file is not None and self.template_file.endswith(".xopp"):
            full_path = os.path.expanduser(self.template_file)
        return os.path.isfile(full_path)

    @action(_("_Xournalpp drawing"), accelerator="<ctrl>m", menuhints="insert:Drawing")
    def Xournalpp(self):
        if not self.is_xopp_dir_valid():
            raise AssertionError("Invalid Xopp directory")
            return

        self.template_valid = self.is_template_file_valid()
        # self.setup_dialog()
        self.run_xournalpp()
        last_mod_file_path = self.get_last_modified_file()
        if last_mod_file_path is None:
            print("No recent file found!")  # add as error
            return
        edited_image_path = self.prepare_img(last_mod_file_path)
        # self.show_img_editor()
        self.insert_image(edited_image_path)
        if self.clean_dir_pref:
            self.clean_xopp_dir()

    def setup_dialog(self):
        # Gtk
        self.gui = Dialog(
            self.window, _("Xournalpp Mode"), buttons=None, defaultwindowsize=(300, -1)
        )
        self.gui.resize(300, 100)  # reset size
        self.gui.show_all()

    def run_xournalpp(self):
        try:
            if self.template_valid:
                # open template
                new_file_path = self.copy_template_to_xopp_dir()
                self.xournalpp = Application(xournalppcmd + " " + new_file_path)
            else:
                self.xournalpp = Application(xournalppcmd)
            self.xournalpp.run()
        except ApplicationError:
            # log should have details of failure
            return None, logfile

    def copy_template_to_xopp_dir(self):
        curr_file_path = os.path.expanduser(self.template_file)
        dest_file_path = os.path.join(
            os.path.expanduser(self.xopp_dir), str(uuid.uuid4()) + ".xopp"
        )  # generate random file_name
        shutil.copy(curr_file_path, dest_file_path)
        print("hello")
        return dest_file_path

    def get_last_modified_file(self):
        full_path = os.path.expanduser(self.xopp_dir)
        full_path = os.path.join(full_path, "")  # to add trailing slash if not present
        files_list = glob.glob(
            full_path + "*.xopp"
        )  # * means all if need specific format then *.csv
        if files_list is None:
            return
        recent_file = max(files_list, key=os.path.getctime)
        return recent_file

    def prepare_img(self, xopp_file):
        # get png file out of xopp
        # raw_img_file_name = os.path.basename(xopp_file)[:-5] + ".png"
        # self.tmp_file = TmpFile(raw_img_file_name)
        raw_img_file = xopp_file[:-5] + ".png"
        xopp2png_cmd = ("xournalpp", xopp_file, "-i", raw_img_file)
        self.xournalpp = Application(xopp2png_cmd)
        self.xournalpp.run()

        # make the image transparent
        transparent_img_file = raw_img_file  # in place edit
        transparent_img_cmd = (
            "convert",
            raw_img_file,
            "-transparent",
            "white",
            transparent_img_file,
        )
        self.imagemagick = Application(transparent_img_cmd)
        self.imagemagick.run()

        # crop off unused spaces from image
        cropped_transparent_img_file = transparent_img_file  # in place edit
        cropped_transparent_img_cmd = (
            "convert",
            transparent_img_file,
            "-fuzz",
            "1%",
            "-trim",
            "+repage",
            cropped_transparent_img_file,
        )
        self.imagemagick = Application(cropped_transparent_img_cmd)
        self.imagemagick.run()

        return cropped_transparent_img_file

    def show_img_editor(self):
        print("placeholder")

    def clean_xopp_dir(self):
        full_path = os.path.expanduser(self.xopp_dir)
        test = os.listdir(full_path)
        for file in test:
            if file.endswith(".xopp") or file.endswith(".png"):
                os.remove(os.path.join(full_path, file))

    def insert_image(self, curr_file_path):
        page = self.window.pageview.page
        notebook = self.window.notebook
        dest_dir = notebook.get_attachments_dir(page)
        dest_file_name = os.path.basename(curr_file_path)
        dest_file_path = os.path.join(dest_dir.path, dest_file_name)
        shutil.copy(curr_file_path, dest_file_path)
        self.window.pageview.insert_image(File(dest_file_path))

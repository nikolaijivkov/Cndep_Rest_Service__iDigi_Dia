#!/usr/bin/python2.4

############################################################################
#                                                                          #
# Copyright (c)2008, 2009, Digi International (Digi). All Rights Reserved. #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing     #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,      #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################

"""\
To run this, use command line: python dia.py [config.yml]
"""

# imports
import sys
try:
    import os.path
except:
    # os comes from python.zip on our gateways.
    print """\
Unable to import 'os' module. Check that your system has a 'python.zip' file,\r
and that it is the correct one for your device.\r
"""
    sys.exit(1)

import time
import gc
import StringIO

# exceptions
class DiaSettingsFileNotFound(Exception):
    pass

# constants
DIGI_DIA_BOOTSTRAP_VERSION = "1.4.14"
DIGI_PYTHON_VERSION_PYTHON_ZIP_PN_MAP = {
    (2, 4): ["40002643_B", "83000001-02"],
    (2, 6): ["83000001-20"],
}
DIGI_WEB_FS_PATH = 'WEB/python'
DIGI_DIA_ARCHIVE = os.path.join(DIGI_WEB_FS_PATH, "dia.zip")
DEFAULT_SETTINGS_DIGIPLATFORM_BASENAME = "dia.pyr"
DEFAULT_SETTINGS_PCPLATFORM_BASENAME = "dia.yml"
GC_COLLECTION_INTERVAL = 60 * 15 # fifteen minutes

# internal functions & classes
def version_tuple_to_str(version_tuple):
    return '.'.join(map(lambda i: str(i), version_tuple[0:3]))


def check_for_dia_zip_and_version(digi_dia_archive):
    """
Verifies that dia.zip is found, compiled against the same Python version,
and finally returns the Dia version found.
Throws an exception on error, otherwise returns the Dia version.
    """

    # Verify dia.zip exists.
    if digi_dia_archive and not os.path.exists(digi_dia_archive):
        print "Error: required file '%s' is missing!" % (digi_dia_archive)
        print ""
        print "Startup halted."
        raise

    # Dia.zip must contain zipfile, if we are unable to import it,
    # either the dia.zip is corrupt, or was compiled against the wrong
    # version of Python.
    try:
        import zipfile
    except Exception:
        pyver = version_tuple_to_str(sys.version_info)

        print "Error: unable to load required library!"
        print "Check to make sure that '%s' is not corrupt." % \
              (digi_dia_archive)
        print "Also verify that it was compiled against Python %s" % (pyver)
        print ""
        print "Startup halted."
        raise

    # Attempt to get dia version.
    try:
        from common.dia_version import DIA_VERSION
    except:
        print "Error: DIA_VERSION does not exist!"
        print "Check if dia FS is corrupt or if %s is missing." % \
            (digi_dia_archive)
        print ""
        print "Startup halted."
        raise

    # Verify Dia version is what we expect.
    if DIA_VERSION != DIGI_DIA_BOOTSTRAP_VERSION:
        print "Error: Bootstrap and dia_version module version mis-match!"
        print "dia.py version is '%s' library version is '%s'" % \
            (DIGI_DIA_BOOTSTRAP_VERSION, DIA_VERSION)
        print "Please check if dia.py and digi_dia libraries match."
        print "You may need to update your dia.py or digi_dia.zip files."
        print ""
        print "Startup halted."
        raise

    return DIA_VERSION

def check_python_zip_version():
    """
Verifies that python.zip is the correct version on the Digi platform.
    """
    version_buf = None

    try:
        # Extract version from python_zip module in python.zip
        # This is available in python.zip versions 83000001-02 and greater.
        from python_zip import VERSION
        version_buf = VERSION
    except:
        pass

    try:
        if not version_buf:
            import zipfile

            if version_buf:
                # shortcut
                raise Exception
            python_zip_flo = open(
                                os.path.join(DIGI_WEB_FS_PATH, 'python.zip'),
                                'rb')
            python_zip = zipfile.ZipFile(python_zip_flo)
            version_buf = python_zip.read('VERSIONS.txt')
            try:
                version_buf = version_buf[version_buf.index('40002643'):]
            except:
                version_buf = version_buf[version_buf.index('83000001'):]
            version_buf = version_buf[0:version_buf.index(' ')]
            python_zip.close()
    except Exception, e:
        print "failed: %s" % str(e)
        pass

    if not version_buf:
        # Our default, assumed version:
        version_buf = "40002643_A"

    accepted_versions = DIGI_PYTHON_VERSION_PYTHON_ZIP_PN_MAP[
                            sys.version_info[0:2]]
    if version_buf not in accepted_versions:
        print "python.zip version too old!"
        print "Found version %s need %s." % \
            (version_buf, ' or '.join(accepted_versions))
        print "Please see: http://ftp1.digi.com/support/sampleapplications/"
        print "download %s.zip from the above URL, rename it to" % \
            (accepted_versions[len(accepted_versions)-1])
        print "python.zip, upload it to the gateway under "
        print "Applications->Python using the web interface and reboot"
        print "the gateway."
        print ""
        print "Startup halted."
        return False

    return True

def open_dia_zip_settings_file():
    """
Open the default Dia binary archive and extract the default settings
file from it.
    """
    try:
        import zipfile

    except Exception, e:
        print "Unable to import zipfile module: %s" % str(e)

    try:
        print 'Attempting to read "%s" in "%s"...' % \
            (DEFAULT_SETTINGS_DIGIPLATFORM_BASENAME, DIGI_DIA_ARCHIVE)
        dia_zip_flo = open(DIGI_DIA_ARCHIVE, 'rb')
        dia_zip = zipfile.ZipFile(dia_zip_flo)
        settings_buf = dia_zip.read(DEFAULT_SETTINGS_DIGIPLATFORM_BASENAME)
        dia_zip.close()
        settings_flo = StringIO.StringIO(settings_buf)
    except Exception, e:
        print "Unable to open settings file in archive: %s" % str(e)
        raise DiaSettingsFileNotFound

    return settings_flo


def spin_forever(core):
    """\
    This routine prevents the main thread from exiting when the
    framework is run directly from __main__.
    """
    while not core.shutdown_requested():
        n = gc.collect()
        if n:
            # only print if something accomplished
            print "GarbageCollector: collected %d objects." % n
        core.wait_for_shutdown(GC_COLLECTION_INTERVAL)

    core._shutdown()
    print "dia.py is exiting...\n"

def main():
    # command line parameter(s):
    settings_file = DEFAULT_SETTINGS_DIGIPLATFORM_BASENAME

    # were we given a settings file?
    settings_file_given = False

    # settings file file-like object:
    settings_flo = None

    # parse command line parameters:
    if sys.argv and len(sys.argv) > 1:
        # settings file:
        settings_file = sys.argv[1]
        settings_file_given = True

    # Determine platform, add modules to import path appropriate for platform:
    print "Determining platform type...",
    if sys.platform.startswith('digi'):
        print "Digi Python environment found.\n"

        if DIGI_DIA_ARCHIVE not in sys.path:
            sys.path.insert(0, DIGI_DIA_ARCHIVE)
        sys.path.insert(0, os.path.join(DIGI_DIA_ARCHIVE, "src"))
        sys.path.insert(0, os.path.join(DIGI_DIA_ARCHIVE, "lib"))

        try:
            DIA_VERSION = check_for_dia_zip_and_version(DIGI_DIA_ARCHIVE)
        except:
            return 0

        if not check_python_zip_version():
            return 0

        if not os.path.exists(settings_file):
            # try to prepend the WEB FS directory to find the settings:
            settings_file = os.path.join(DIGI_WEB_FS_PATH, settings_file)

        try:
            settings_flo = open(settings_file, 'r')
        except:
            if settings_file_given:
                raise DiaSettingsFileNotFound

        if not settings_flo:
            # Extract the settings from the ZIP archive:
            try:
                settings_flo = open_dia_zip_settings_file()
            except:
                raise DiaSettingsFileNotFound
    elif sys.platform.startswith('digiSarOS'):
        print "Digi Sarian Python environment found.\n"
        dia_archive_name = 'dia.zip'
        if dia_archive_name not in sys.path:
            sys.path.insert(0, dia_archive_name)
        
        sys.path.insert(0, os.path.join(dia_archive_name, "src"))
        sys.path.insert(0, os.path.join(dia_archive_name, "lib"))

        try:
            DIA_VERSION = check_for_dia_zip_and_version(dia_archive_name)
        except:
            return 0
        
        if not check_python_zip_version():
            return 0
        
        if not os.path.exists(settings_file):
            settings_file = os.path.join('.', settings_file)
        
        try:
            settings_flo = open(settings_file, 'r')
        except:
            if settings_file_given:
                raise DiaSettingsFileNotFound
        
        if not settings_flo:
            try:
                settings_flo = open_dia_zip_settings_file()
            except:
                raise DiaSettingsFileNotFound
    else:
        print "PC host environment assumed.\n"
        if sys.version_info[0:2] not in DIGI_PYTHON_VERSION_PYTHON_ZIP_PN_MAP:
            digi_versions = [ version_tuple_to_str(v) for v in 
                                DIGI_PYTHON_VERSION_PYTHON_ZIP_PN_MAP ]
            digi_versions = ' or '.join(digi_versions)
            print "Python version mismatch! Digi='%s', Current='%s'" % \
                (digi_versions, version_tuple_to_str(sys.version_info))
                
        if not settings_file_given:
            settings_file = DEFAULT_SETTINGS_PCPLATFORM_BASENAME
            
        if not os.path.exists(settings_file):
            # try to prepend the cfg directory on PCs to find the settings:
            settings_file = os.path.join('./cfg', settings_file)
        try:
            settings_flo = open(settings_file, 'r')
        except:
            raise DiaSettingsFileNotFound
        for path in ['./lib', './src']:
            sys.path.insert(0, path)

        try:
            DIA_VERSION = check_for_dia_zip_and_version(None)
        except:
            return 0

    print "iDigi Device Integration Application Version %s" % (DIA_VERSION)
    print "Using settings file: %s" % (os.path.split(settings_file)[1])

    from core.core_services import CoreServices

    core = CoreServices(settings_flo=settings_flo,
                        settings_filename=settings_file)

    if __name__ == "__main__":
        # Don't exit.  If not __main__ then the caller needs to guarantee this.
        spin_forever(core)

    return core

if __name__ == "__main__":
    status = main()
    sys.exit(status)

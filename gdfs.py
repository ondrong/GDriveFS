#!/usr/bin/python

import fuse
import stat
import logging
import dateutil.parser
import getpass
import os

from time       import mktime
from argparse   import ArgumentParser

from gdtool import drive_proxy, get_auth
from utility import get_utility
from cache import get_cache

if not hasattr(fuse, '__version__'):
    raise RuntimeError, \
        "Your fuse-py doesn't know of fuse.__version__, probably it's too old."

fuse.fuse_python_api = (0, 2)

app_name = 'GDriveFS Tool'

class _GDriveStat(fuse.Stat):
    """A skeleton stat() structure."""

    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0

class _GDriveFS(fuse.Fuse):
    """The main filesystem class."""

    def getattr(self, path):
        """Return a stat() structure."""

        logging.info("Stat() on [%s]." % (path))

# TODO: !! If the listed directory is '/', it will be enumerated first, and then all of the entries stat()'d. If it's a subdirectory, first the token will be stat()'d, -then- its entries are enumerated. We need to pull the listing here, is not already loaded. SEE NEXT COMMENT.

        is_folder = False
        if path == '/':
            is_folder = True

        else:
# TODO: We need to access the wrapper instead of the cache so that it can get the information if it's not cached.
            try:
                entry = get_cache().get_entry_by_filepath(path)
            except:
                logging.exception("Could not find entry in cache for path [%s]." % (path))
                raise

            is_folder = get_utility().is_folder(entry)

        st = _GDriveStat()

        if is_folder:
            st.st_mode = stat.S_IFDIR | 0755
            st.st_nlink = 2

        else:
            date_obj = dateutil.parser.parse(entry[u'modifiedDate'])
            mtime_epoch = mktime(date_obj.timetuple())

            st.st_mode = stat.S_IFREG | 0444
            st.st_nlink = 1

            if u'quotaBytesUsed' in entry:
                st.st_size = int(entry[u'quotaBytesUsed'])
            else:
                st.st_size = 0
            
            st.st_mtime = mtime_epoch

#        else:
#            return -errno.ENOENT

        return st

    def readdir(self, path, offset):
        """A generator returning one base filename at a time."""

        logging.info("ReadDir(%s,%d) invoked." % (path, offset))

        # We expect "offset" to always be (0).
        if offset != 0:
            logging.warning("readdir() has been invoked for path [%s] and non-"
                            "zero offset (%d). This is not allowed." % 
                            (path, offset))

# TODO: Return -ENOENT if not found?
# TODO: Once we start working on the cache, make sure we don't make this call, 
#       constantly.

        logging.debug("Listing files.")

        try:
            drive_proxy('list_files')
        except:
            logging.exception("Could not get list of files.")
            raise

        try:
            file_cache = get_cache()
        except:
            logging.exception("Could not acquire cache.")
            raise

        logging.debug("Retrieving children for path [%s]." % (path))

        try:
            children = file_cache.get_children_by_path(path)
        except:
            children = []
            logging.exception("There was an exception when retrieving children"
                              " for path [%s]." % (path))

        id_list_string = ', '.join(children)
        logging.debug("Rendering paths for children: %s" % (id_list_string))

        try:
            filepaths = file_cache.get_filepaths_for_entries(children)
        except:
            logging.exception("There was a problem producing the list of file-paths.")
            filepaths = { }

        filenames = ['.','..']
        for filepath in filepaths.itervalues():
            filenames.append(os.path.basename(filepath))

        for filename in filenames:
            yield fuse.Direntry(filename)

#    def fsinit(*args): 
#        import syslog
#        syslog.openlog('myfs') 
#        syslog.syslog("INIT") 
#        syslog.closelog() 
#
#    def destroy(self, path):
#        with open('/tmp/destroy', 'w') as f:
#            f.write("Content.")
#
#        import syslog
#        syslog.openlog('myfs2') 
#        syslog.syslog("DESTROY (2)") 
#        syslog.closelog()

def dump_changes(overview):
    (largest_change_id, next_page_token, changes) = overview

    for change_id, change in changes.iteritems():
        (file_id, was_deleted, entry) = change
        print("%s> %s" % (change_id, entry[u'title']))

#    print(changes)

def main():
    #change_overview = drive_proxy('list_changes')
    #dump_changes(change_overview)
    #files = drive_proxy('list_files')

    #return
    usage="""GDriveFS Fuser\n\n""" + fuse.Fuse.fusage
    server = _GDriveFS(version="%prog " + fuse.__version__,
                      usage=usage,
                      dash_s_do='setsingle')

#    server.parser.add_option(mountopt='ac', metavar="FILEPATH",
#                             help="API Credentials JSON file-path.")
#    server.parser.add_option('-a', '--ac', metavar="FILEPATH", 
#                             help="API Credentials JSON file-path.")

    fuse_args = server.parse(errex=1)

    server.main()

if __name__ == "__main__":
    main()


#!/usr/bin/env python3

# This is part of the IFDB-Archive integration. Here's how it works:
#
# When someone uses the "upload to IF archive" flow on IFDB, it creates
# a "pending" upload link on IFDB. It also hands the upload to us with
# a one-off ID key. (This is not the TUID, by the way.)
#
# Later, we run this script, which passes the final Archive path back
# to IFDB, along with the ID. IFDB can then update the pending link.
# The IFDB form URL used for this purpose is:
#
# http://ifdb.org/ifarchive-commit?ifdbid=XXX&path=PPP&key=SECRET
#
# The data shared between upload.py and this script is stored in a
# Python "shelve" file (see ifdbIdFile). The format is a dict mapping
#   filemd5: { 'time':timestamp, 'id':ifdbid }
# For historical reasons we are still on shelve/pickle protocol 2.

import os, os.path, shelve, hashlib, urllib.request

def submitID(fns, askForID = False):
    ifdbIdFile = "/var/ifarchive/lib/ifids"
    # ifdbKey is a real access key in production
    ifdbKey = 'XXX'
    ifdbUrl = "https://ifdb.org/ifarchive-commit?ifdbid={ifdbid}&path={path}&key={key}"
    dirPrefix = '/var/ifarchive/htdocs' # Prefix to remove from a file's abspath

    for fn in fns:
        # Get the directory and base name of the file
        absfn = os.path.realpath(os.path.abspath(fn))
        if not os.path.isfile(absfn):
            continue
        (pathfn, basefn) = os.path.split(absfn)
        
        # See if an IFDB ID exists for the file (based on its md5 hash)
        o = open(fn, "rb")
        hashval = hashlib.md5(o.read()).hexdigest()
        o.close()

        # We gotta play with the umask to open shelve
        ifdbID = None
        oldmask = os.umask(0)
        ids = shelve.open(ifdbIdFile, protocol=2)
        if hashval in ids:
            ifdbID = ids[hashval]['id']
        ids.close()
        # Reset umask
        os.umask(oldmask)
        
        # If not, query for the IFDB ID interactively (sometimes)
        if ifdbID is None:
            if askForID:
                ifdbID = input("IFDB ID for %s: "% basefn)
                # If no ID is passed, stop
                if not ifdbID:
                    return
            else:
                print("No IFID found for "+fn)
                return

        # Massage the directory to fit what IFDB needs
        ifdbPath = absfn
        if ifdbPath.startswith(dirPrefix):
            ifdbPath = ifdbPath[len(dirPrefix):]

        # Submit the directory to IFDB
        urlToFetch = ifdbUrl.format(ifdbid=ifdbID, path=ifdbPath, key=ifdbKey)
        ifdbPage = urllib.request.urlopen(urlToFetch)
        resultStr = ifdbPage.readline()
        ifdbPage.close()
        # The ifdb update page returns plain text from the following list:
        #   OK
        #   Error: invalid API key
        #   Error: no link found to this pending URL
        #   Error: database update failed: <db error message>
        if resultStr == 'OK':
            print("IFDB updated for %s (ID %s)\n" % (fn, ifdbID))
        elif resultStr.startswith('Error: '):
            print("IFDB update for %s failed. %s" % (fn, resultStr))
        else:
            print("IFDB update for %s failed unexpectedly: %s" % (fn, resultStr))


if __name__ == "__main__":
    import optparse
    
    p = optparse.OptionParser(usage="%prog [file(s) to submit to IFDB]")
    p.add_option("-n", "--non-interactive", action="store_false",
                 dest="askForID", help="don't ask the user to enter an ID")
    p.add_option("-i", "--interactive", action="store_true",
                 dest="askForID",
                 help="ask the user to enter an ID if no stored one is found [default]")
    p.set_defaults(askForID = True)
    (options, args) = p.parse_args()

    if len(args) == 0:
        p.error("No filenames to submit to IFDB. Type --help for more information.")
    
    submitID(args, options.askForID)

# upload.py -- CGI script that handles IF Archive file uploads

- Copyright 2017 by the Interactive Fiction Technology Foundation
- Not publicly distributed
- Created by Andrew Plotkin <erkyrath@eblong.com>

This script runs the web form which accepts IF Archive file uploads.

HTML pages are generated from the templates in the lib directory. The templating mechanism is as simple as it could be -- constant substring of the form "{tag}" are replaced by other constant strings. (This is much simpler than the templating mechanism in the ifarchive-ifmap-py repository.)

As a matter of minimal security, we don't let the public see this repository or this script. It might not be a big deal; the only "secret" information is the maximum upload size. But we might as well not worry about jerks gaming it.


# upload.py -- CGI script that handles IF Archive file uploads

- Copyright 2017-23 by the Interactive Fiction Technology Foundation
- Distributed under the MIT license
- Created by Andrew Plotkin <erkyrath@eblong.com>

This script runs the web form which accepts IF Archive file uploads.

HTML pages are generated from the templates in the lib directory. The templating mechanism is as simple as it could be -- constant substring of the form "{tag}" are replaced by other constant strings. (This is much simpler than the templating mechanism in the ifarchive-ifmap-py repository.)

(This repository was made public in 2023. It never really contained anything secret.)


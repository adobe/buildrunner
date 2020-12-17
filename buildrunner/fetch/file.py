'''
Fetch files from the file system.

Copyright (C) 2020 Adobe
'''

import codecs


def fetch_file(parsed_url, config):
    '''
    Pull files from the local file system.
    '''
    with codecs.open(parsed_url.path, 'r', encoding='utf-8') as _file:
        contents = ''.join(_file.readlines())

    return contents


# Local Variables:
# fill-column: 100
# End:

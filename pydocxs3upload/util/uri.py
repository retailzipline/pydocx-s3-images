from __future__ import (
    unicode_literals,
)

import posixpath
import re

from six.moves.urllib.parse import unquote

regexp_pattern = r'data:image/(?P<extension>\w+);base64,(?P<image_data>.+)'

IMAGE_DATA_URI_REGEX = {
    'bytes': re.compile(regexp_pattern.encode()),
    'str': re.compile(regexp_pattern),
}


def is_encoded_image_uri(image_data):
    """Check if input is a image data format"""

    if isinstance(image_data, bytes):
        regex = IMAGE_DATA_URI_REGEX['bytes']
    else:
        regex = IMAGE_DATA_URI_REGEX['str']

    return regex.match(image_data)


def sanitize_filename(filename):
    """
    When we create attachments from pydocx we usually add a timestamp followed
    by a dash (-) to make the image unique for round-tripping. In an effort to
    prevent a bunch of timestamps preceding the image name (in the event a
    document is round-tripped several times), strip off the timestamp
    and dash. When images come from docx they are always `image{N}`. We only
    want to strip off the timestamp and dash if they were programmatically
    added.
    """

    # (timestamp)-image(image_number).(file_extension)
    regex = re.compile(r'\d{10}-image\d+\.\w{3,4}')
    if regex.match(filename):
        _, filename = filename.rsplit('-', 1)

    return unquote(filename)


def get_uri_filename(uri):
    _, filename = posixpath.split(uri)

    return filename


def uri_is_internal(uri):
    return uri.startswith('/')


def uri_is_external(uri):
    return not uri_is_internal(uri)


def uri_is_self_hosted(uri, bucket_name=''):
    s3_bucket_url = "https://%s.s3.amazonaws.com" % (bucket_name)
    return uri.startswith(s3_bucket_url)

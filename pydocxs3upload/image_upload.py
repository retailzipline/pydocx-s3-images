# coding: utf-8
from __future__ import (
    absolute_import,
    unicode_literals,
)

import base64
import json
from xml.etree import ElementTree

import requests
import six
from six.moves.urllib.parse import unquote

from .exceptions import ImageUploadException
from .util import uri, image


class ImageUploader(object):
    def upload(self, *args, **kwargs):
        raise NotImplementedError("Implement upload method")


def is_xml(string):
    try:
        ElementTree.fromstring(string)
    except ElementTree.ParseError:
        return False
    return True


def location_value(bytes):
    if is_xml(bytes.decode('utf-8')):
        element_body = ElementTree.fromstring(bytes)
        location_element = element_body.find("Location")

        if location_element is not None:
            return location_element.text
        else:
            return None
    else:
        return None


class S3ImageUploader(ImageUploader):
    def __init__(self, signed_data):
        if isinstance(signed_data, six.string_types):
            signed_data = json.loads(signed_data)

        self.signed_data = signed_data

        self._bucket_name = None
        self._s3_url = None

        self.OK_STATUS = [201, 204]
        self.S3_ERROR_STATUS = 403

        self.AWS_URL = 'https://{bucket_name}.s3.amazonaws.com/'

    @property
    def s3_url(self):
        """Get s3 url from signed request. If not found, use default one"""

        if not self._s3_url:
            default = self.AWS_URL.format(bucket_name=self.bucket_name)
            self._s3_url = self.signed_data.pop('url', default)

        return self._s3_url

    @property
    def bucket_name(self):
        """Find the bucket name from input signed request data"""

        if not self._bucket_name:
            decoded_data = base64.b64decode(self.signed_data['policy'])
            policy_data = json.loads(decoded_data)

            bucket_name = None

            for item in policy_data['conditions']:
                if isinstance(item, dict) and item.get('bucket', None):
                    bucket_name = item['bucket']
                    break

            self._bucket_name = bucket_name

        return self._bucket_name

    @classmethod
    def image_data_decode(cls, image_data):
        """
        We can have image data in multiple formats: binary
        or as image data base64 encoded
        """

        match = uri.is_encoded_image_uri(image_data)
        if match:
            image_data = base64.b64decode(match.group('image_data'))

        return image_data

    def upload(self, img_data, filename, image_format=None):
        """Upload image to amazon s3"""

        # make sure that we decode base64 encoded images
        img_data = self.image_data_decode(img_data)

        image_format = image_format or image.get_image_format(filename)

        data = self.signed_data

        url = self.s3_url

        if 'storage.googleapis.com' not in url:
            data['Content-Type'] = 'image/%s' % image_format

        r = requests.post(url, data=data, files={'file': (filename, img_data)})

        if r.status_code == self.S3_ERROR_STATUS:
            error = ElementTree.fromstring(r.content)
            code = error.find("Code").text
            message = error.find("Message").text

            raise ImageUploadException("S3 {0} - {1}".format(code, message))
        elif r.status_code not in self.OK_STATUS:
            raise ImageUploadException("S3 Upload Error: {0}".format(r.text))

        # AWS returns the object URL in a location header when 204 is given
        # as the success action
        if r.status_code == 204:
            image_url = r.headers.get('location', None)
            if image_url:
                return unquote(image_url)

        # GCS does not return a location header for 204 so, we must use 201
        # and the body content
        if r.status_code == 201:
            image_url = location_value(r.content)
            if image_url:
                return image_url

        raise ImageUploadException("S3 Invalid location header")

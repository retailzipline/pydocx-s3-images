# coding: utf-8
from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

from unittest import TestCase
import json

import responses
from responses.matchers import multipart_matcher

from pydocxs3upload.exceptions import ImageUploadException
from pydocxs3upload.image_upload import S3ImageUploader, ImageUploader
from pydocxs3upload.test.utils import get_fixture, mock_request


def get_signed_request():
    signed_request = get_fixture('upload_signed_request.json', as_binary=True)
    signed_request = json.loads(signed_request)

    return signed_request


class ImageUploaderTestCase(TestCase):
    def test_upload(self):
        iu = ImageUploader()

        with self.assertRaises(NotImplementedError):
            iu.upload()


class S3ImageUploaderTestCase(TestCase):
    def test_input_as_json(self):
        signed_request = get_fixture('upload_signed_request.json', as_binary=True)

        s3 = S3ImageUploader(signed_request)

        self.assertIsInstance(s3.signed_data, dict)

    def test_input_as_dict(self):
        signed_request = get_fixture('upload_signed_request.json', as_binary=True)
        signed_request = json.loads(signed_request)

        s3 = S3ImageUploader(signed_request)

        self.assertIsInstance(s3.signed_data, dict)

    @responses.activate
    def test_upload_image(self):
        mock_request()

        signed_request = get_signed_request()

        s3 = S3ImageUploader(signed_request)

        img_data = get_fixture('image1.png', as_binary=True)

        result = s3.upload(img_data, 'image2.png', 'png')

        self.assertEqual('http://pydocx.s3.amazonaws.com/uploads/pydocx/image2.png', result)

    @responses.activate
    def test_upload_image_missing_url(self):
        mock_request(url='https://pydocx.s3.amazonaws.com/')

        signed_request = get_signed_request()

        # it will use the default url instead
        del signed_request['url']

        s3 = S3ImageUploader(signed_request)

        img_data = get_fixture('image1.png', as_binary=True)

        result = s3.upload(img_data, 'image1.png')

        self.assertEqual('https://pydocx.s3.amazonaws.com/uploads/pydocx/image1.png', result)

    @responses.activate
    def test_upload_image_invalid_bucket_url(self):
        mock_request(url='http://invalid_bucket.s3.amazonaws.com/', status=403,
                     fixture='s3_invalid_response.xml')

        signed_request = get_signed_request()

        signed_request['url'] = 'http://invalid_bucket.s3.amazonaws.com/'

        s3 = S3ImageUploader(signed_request)

        img_data = get_fixture('image1.png', as_binary=True)

        with self.assertRaisesRegexp(ImageUploadException,
                                     'S3 NoSuchBucket - The specified bucket does not exist'):
            s3.upload(img_data, 'image2.png', 'png')

    @responses.activate
    def test_upload_image_invalid_response(self):
        mock_request(status=404)

        signed_request = get_signed_request()

        signed_request['url'] = 'http://pydocx.s3.amazonaws.com/'

        s3 = S3ImageUploader(signed_request)

        img_data = get_fixture('image1.png', as_binary=True)

        with self.assertRaisesRegexp(ImageUploadException, 'S3 Upload Error'):
            s3.upload(img_data, 'image1.png')

    @responses.activate
    def test_upload_image_invalid_signed_request(self):
        mock_request(status=403, fixture='s3_invalid_access_key.xml')

        signed_request = get_signed_request()

        signed_request['AWSAccessKeyId'] += 'test'

        s3 = S3ImageUploader(signed_request)

        img_data = get_fixture('image1.png', as_binary=True)

        with self.assertRaisesRegexp(ImageUploadException, 'S3 InvalidAccessKeyId '):
            s3.upload(img_data, 'image3.png', 'png')

    @responses.activate
    def test_upload_image_as_data(self):
        mock_request()

        signed_request = get_signed_request()

        s3 = S3ImageUploader(signed_request)

        img_data = get_fixture('image1.data', as_binary=True)

        result = s3.upload(img_data, 'image4.jpg')

        self.assertEqual('http://pydocx.s3.amazonaws.com/uploads/pydocx/image4.jpg', result)

    @responses.activate
    def test_upload_image_invalid_location_header(self):
        mock_request(include_location=False)

        signed_request = get_signed_request()

        s3 = S3ImageUploader(signed_request)

        img_data = get_fixture('image1.png', as_binary=True)

        with self.assertRaisesRegexp(ImageUploadException, 'S3 Invalid location header'):
            s3.upload(img_data, 'image4.png')

class GCSImageUploaderTestCase(TestCase):
    @responses.activate
    def test_content_type_not_set_when_gcs_url(self):
        filename = 'image1.png'
        image_data = get_fixture(filename, as_binary=True)
        xml_body = get_fixture('gcs_success_response.xml', as_binary=True)

        signed_request = get_signed_request()
        signed_request['url'] = 'https://pydocx.storage.googleapis.com'

        signed_mock = get_signed_request()
        signed_mock.pop('url')
        files = {"file": (filename, image_data)}
        responses.add(responses.POST,
                      signed_request['url'],
                      status=201,
                      match=[multipart_matcher(files, data=signed_mock)],
                      content_type='multipart/form-data',
                      body=xml_body)

        S3ImageUploader(signed_request).upload(image_data, filename, 'png')

    @responses.activate
    def test_fails_when_gcs_url_with_204_status_code(self):
        filename = 'image1.png'
        image_data = get_fixture(filename, as_binary=True)

        signed_request = get_signed_request()
        signed_request['url'] = 'https://pydocx.storage.googleapis.com'

        signed_mock = get_signed_request()
        signed_mock.pop('url')
        files = {"file": (filename, image_data)}
        responses.add(responses.POST,
                      signed_request['url'],
                      status=204,
                      match=[multipart_matcher(files, data=signed_mock)],
                      content_type='multipart/form-data')

        with self.assertRaisesRegexp(ImageUploadException, 'S3 Invalid location header'):
            S3ImageUploader(signed_request).upload(image_data, filename, 'png')


    @responses.activate
    def test_object_url_returned_when_gcs_url(self):
        filename = 'image1.png'
        image_data = get_fixture(filename, as_binary=True)
        xml_body = get_fixture('gcs_success_response.xml', as_binary=True)

        signed_request = get_signed_request()
        signed_request['url'] = 'https://pydocx.storage.googleapis.com'

        signed_mock = get_signed_request()
        signed_mock.pop('url')
        files = {"file": (filename, image_data)}
        responses.add(responses.POST,
                      signed_request['url'],
                      status=201,
                      match=[multipart_matcher(files, data=signed_mock)],
                      content_type='multipart/form-data',
                      body=xml_body)

        expected_url = 'https://storage.googleapis.com/urkle/o/zipline/communications/626f40b5-3b6b-4f58-bb76-312400168b4c/16692490480691016-image1.png'
        result = S3ImageUploader(signed_request).upload(image_data, filename, 'png')
        self.assertEqual(expected_url, result)

    @responses.activate
    def test_fails_when_gcs_url_and_no_location_element(self):
        filename = 'image1.png'
        image_data = get_fixture(filename, as_binary=True)
        xml_body = get_fixture('gcs_missing_location_element_response.xml', as_binary=True)

        signed_request = get_signed_request()
        signed_request['url'] = 'https://pydocx.storage.googleapis.com'

        signed_mock = get_signed_request()
        signed_mock.pop('url')
        files = {"file": (filename, image_data)}
        responses.add(responses.POST,
                      signed_request['url'],
                      status=201,
                      match=[multipart_matcher(files, data=signed_mock)],
                      content_type='multipart/form-data',
                      body=xml_body)

        with self.assertRaisesRegexp(ImageUploadException, 'S3 Invalid location header'):
            S3ImageUploader(signed_request).upload(image_data, filename, 'png')


    @responses.activate
    def test_fails_when_gcs_url_and_response_body_not_xml(self):
        filename = 'image1.png'
        image_data = get_fixture(filename, as_binary=True)

        signed_request = get_signed_request()
        signed_request['url'] = 'https://pydocx.storage.googleapis.com'

        signed_mock = get_signed_request()
        signed_mock.pop('url')
        files = {"file": (filename, image_data)}
        responses.add(responses.POST,
                      signed_request['url'],
                      status=201,
                      match=[multipart_matcher(files, data=signed_mock)],
                      content_type='multipart/form-data',
                      body="Howdy!")

        with self.assertRaisesRegexp(ImageUploadException, 'S3 Invalid location header'):
            S3ImageUploader(signed_request).upload(image_data, filename, 'png')

    @responses.activate
    def test_fails_when_gcs_url_and_error_response(self):
        filename = 'image1.png'
        image_data = get_fixture(filename, as_binary=True)
        xml_body = get_fixture('gcs_invalid_policy_response.xml', as_binary=True)

        signed_request = get_signed_request()
        signed_request['url'] = 'https://pydocx.storage.googleapis.com'

        signed_mock = get_signed_request()
        signed_mock.pop('url')
        files = {"file": (filename, image_data)}
        responses.add(responses.POST,
                      signed_request['url'],
                      status=400,
                      match=[multipart_matcher(files, data=signed_mock)],
                      content_type='multipart/form-data',
                      body=xml_body)

        with self.assertRaises(ImageUploadException) as capture:
            S3ImageUploader(signed_request).upload(image_data, filename, 'png')
        exception = str(capture.exception)

        expected_message = "S3 Upload Error: {0}".format(xml_body)
        self.assertEqual(exception, expected_message)

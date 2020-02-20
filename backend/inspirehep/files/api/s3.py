# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

import structlog
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError
from werkzeug import secure_filename

LOGGER = structlog.getLogger()


class S3:
    def __init__(
        self,
        client,
        resource,
        config=None,
        s3_bucket_prefix=None,
        s3_hostname=None,
        s3_file_acl=None,
    ):
        self.client = client
        self.resource = resource
        if not config:
            config = TransferConfig(max_concurrency=1, use_threads=False)
        self.config = config
        self.s3_bucket_prefix = s3_bucket_prefix
        self.s3_hostname = s3_hostname
        self.s3_file_acl = s3_file_acl

    def get_bucket_for_file_key(self, key):
        """Return the bucket for the given file key.

        :param key: the file key
        :return: bucket: The corresponding bucket.
        """
        return self.get_prefixed_bucket(key[0])

    def get_prefixed_bucket(self, bucket_without_prefix):
        """Returns prefixed bucket for given bucket"""
        return f"{self.s3_bucket_prefix}{bucket_without_prefix}"

    def is_s3_url(self, url):
        """Checks if the url is an S3 url.

        :param url: the given url.
        :return: boolean
        """
        return url.startswith(self.s3_hostname)

    def upload_file(self, data, key, filename, mimetype, acl):
        """Upload a file in s3 bucket with the given metadata

        :param data: the data of the file.
        :param key: the key of the file.
        :param filename: the filename.
        :param mimetype: the mimetype of the file.
        :param acl: the access control list for the file.
        :return: dict
        """
        try:
            response = self.client.upload_fileobj(
                data,
                self.get_bucket_for_file_key(key),
                key,
                ExtraArgs={
                    "ContentType": mimetype,
                    "ACL": acl,
                    "ContentDisposition": self.get_content_disposition(filename),
                },
                Config=self.config,
            )
            return response
        except ClientError as e:
            LOGGER.warning(exc=e, key=key)
            raise

    def delete_file(self, key):
        """Deletes the given file from S3.

        :param key: the key of the file.
        :return: dict
        """
        try:
            response = self.client.delete_object(
                Bucket=self.get_bucket_for_file_key(key), Key=key
            )
            return response
        except ClientError as e:
            LOGGER.warning(exc=e, key=key)
            raise

    def get_file_url(self, key):
        """Returns the S3 link for the file.

        :param key: the key of the file.
        :return: string: the s3 link for the file
        """
        return f"{self.s3_hostname}/{self.get_bucket_for_file_key(key)}/{key}"

    @staticmethod
    def get_content_disposition(filename):
        return f'attachment; filename="{secure_filename(filename)}"'

    def replace_file_metadata(self, key, filename, mimetype, acl):
        """Updates the metadata of the given file.

        :param key: the file key.
        :param filename: the new filename.
        :param mimetype: the new mimetype.
        :param acl: the new access control list for the file.
        :return: dict
        """
        try:
            response = self.client.copy_object(
                ACL=acl,
                Bucket=self.get_bucket_for_file_key(key),
                Key=key,
                CopySource={"Bucket": self.get_bucket_for_file_key(key), "Key": key},
                ContentDisposition=self.get_content_disposition(filename),
                ContentType=mimetype,
                MetadataDirective="REPLACE",
            )
            return response
        except ClientError as e:
            LOGGER.warning(exc=e, key=key)
            raise

    def get_file_metadata(self, key):
        """Returns the metadata of the file.

        :param key: the key of the file.
        :return: the metadata of the file.
        """
        try:
            object_head = self.client.head_object(
                Bucket=self.get_bucket_for_file_key(key), Key=key
            )
            return object_head
        except ClientError as e:
            LOGGER.warning(exc=e, key=key)
            raise

    def file_exists(self, key):
        """Checks if the file is already in S3.

        :param key: the key of the file.
        :return: boolean
        """
        try:
            self.client.head_object(Bucket=self.get_bucket_for_file_key(key), Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                LOGGER.warning(exc=e, key=key)
                raise

    def create_bucket(self, bucket):
        return self.client.create_bucket(
            Bucket=self.get_prefixed_bucket(bucket), ACL=self.s3_file_acl
        )

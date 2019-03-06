# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.
import logging

from elasticsearch.helpers import bulk
from flask import current_app
from invenio_indexer.api import RecordIndexer
from invenio_indexer.signals import before_record_index
from sqlalchemy.orm.exc import NoResultFound

from invenio_search import current_search_client as es

logger = logging.getLogger(__name__)


class InspireRecordIndexer(RecordIndexer):
    """Excend Invenio indexer to properly index Inspire stuff"""

    def _prepare_record(self, record, index, doc_type):
        data = record.dumps_for_es()

        before_record_index.send(
            current_app._get_current_object(),
            json=data,
            record=record,
            index=index,
            doc_type=doc_type,
        )
        return data

    def _process_bulk_record_for_index(
        self, record, version_type="external_gte", index=None, doc_type=None
    ):
        """Process basic data required for indexing record suring bulk indexing

        Args:
            record(InspireRecord): Proper inspire record record object
            version_type(str): Proper ES versioning type:
                * internal
                * external
                * external_gt
                * external_gte

        Returns:
            dict: dict with preprocessed record for bulk indexing

        """
        _index, _doc_type = self.record_to_index(record)
        if not doc_type:
            doc_type = _doc_type
        if not index:
            index = _index
        return {
            "_op_type": "index",
            "_index": index,
            "_type": doc_type,
            "_id": str(record.id),
            "_version": record.revision_id,
            "_version_type": version_type,
            "_source": self._prepare_record(record, index, doc_type),
        }

    def bulk_index(self, records_uuids, request_timeout=None):
        """Starts bulk indexing for specified records

        Args:
            records_uuids(list[str): List of strings which are UUID's of records
                to reindex
            request_timeout(int): Maximum time after which   es will throw an exception

        Returns:
            dict: dict with success count and failure list
                (with uuids of failed records)

        """
        from inspirehep.records.api import InspireRecord

        def actions():
            for record_uuid in records_uuids:
                try:
                    record = InspireRecord.get_record(record_uuid)
                    if record.get("deleted", False):
                        continue
                    yield self._process_bulk_record_for_index(record)
                except NoResultFound:
                    logger.warning(f"Record {record_uuid} failed to load!")

        if not request_timeout:
            request_timeout = current_app.config["INDEXER_BULK_REQUEST_TIMEOUT"]

        success, failures = bulk(
            es,
            actions(),
            request_timeout=request_timeout,
            raise_on_error=False,
            raise_on_exception=False,
        )

        return {"success": success, "failures": [failure for failure in failures or []]}

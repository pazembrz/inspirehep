import logging

from flask_sqlalchemy import models_committed
from invenio_records.models import RecordMetadata

from inspirehep.pidstore.api import PidStoreBase
from inspirehep.records.api import InspireRecord
from inspirehep.records.errors import WrongOperationOnRecordError
from inspirehep.records.indexer.tasks import index_record


logger = logging.getLogger(__name__)


@models_committed.connect
def index_after_commit(sender, changes):
    """Index a record in ES after it was committed to the DB.

    This cannot happen in an ``after_record_commit`` receiver from Invenio-Records
    because, despite the name, at that point we are not yet sure whether the record
    has been really committed to the DB.
    """
    for model_instance, change in changes:
        logger.debug("index_after_commit hook")
        if isinstance(model_instance, RecordMetadata):
            logger.debug(
                "Model instance (%s) is correct. Processing...", model_instance.id
            )
            if change in ("insert", "update", "delete"):
                logger.debug("Change type is '%s'.", change)
                pid_type = PidStoreBase.get_pid_type_from_schema(
                    model_instance.json.get("$schema")
                )
                delete = "delete" in changes
                arguments = InspireRecord.get_subclasses()[pid_type]._record_index(
                    model_instance.json, _id=str(model_instance.id), deleted=delete
                )
                arguments["record_version"] = model_instance.version_id
                logger.info(f"arguments: {arguments}")
                return index_record.delay(**arguments)
            else:
                raise WrongOperationOnRecordError(
                    f"Wrong operation ({change})on record {model_instance.id}"
                )
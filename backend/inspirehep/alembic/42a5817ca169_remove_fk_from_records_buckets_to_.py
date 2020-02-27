#
# This file is part of Invenio.
# Copyright (C) 2016-2018 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Remove fk from records_buckets to records_metadata"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "42a5817ca169"
down_revision = "f563233434cd"
branch_labels = ()
depends_on = None


def upgrade():
    """Upgrade database."""
    op.execute(
        "ALTER TABLE records_buckets DROP CONSTRAINT fk_records_buckets_record_id_records_metadata"
    )


def downgrade():
    """Downgrade database."""
    op.execute(
        "ALTER TABLE records_buckets ADD CONSTRAINT fk_records_buckets_record_id_records_metadata FOREIGN KEY (record_id) REFERENCES records_metadata(id)"
    )

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';

import LiteratureSearchContainer from '../../literature/containers/LiteratureSearchContainer';
import { CONFERENCE_CONTRIBUTIONS_NS } from '../../reducers/search';
import { getContributionsQueryString } from '../utils';

function ConferenceContributions({ conferenceRecordId }) {
  const baseQuery = useMemo(
    () => ({
      q: getContributionsQueryString(conferenceRecordId),
    }),
    [conferenceRecordId]
  );

  return (
    <LiteratureSearchContainer
      namespace={CONFERENCE_CONTRIBUTIONS_NS}
      baseQuery={baseQuery}
      noResultsTitle="0 Contributions"
    />
  );
}

ConferenceContributions.propTypes = {
  conferenceRecordId: PropTypes.string.isRequired,
};

export default ConferenceContributions;

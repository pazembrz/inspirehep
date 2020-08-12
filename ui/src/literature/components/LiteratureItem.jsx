import React, { Fragment, useContext } from 'react';
import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import { Map } from 'immutable';
import { FilePdfOutlined, FileExclamationTwoTone } from '@ant-design/icons';

import ArxivEprintList from './ArxivEprintList';
import LiteratureDate from './LiteratureDate';
import AuthorsAndCollaborations from '../../common/components/AuthorsAndCollaborations';
import PublicationInfoList from '../../common/components/PublicationInfoList';
import UrlsAction from './UrlsAction';
import DOILinkAction from './DOILinkAction';
import EditRecordAction from '../../common/components/EditRecordAction';
import ResultItem from '../../common/components/ResultItem';
import { LITERATURE } from '../../common/routes';
import LiteratureTitle from '../../common/components/LiteratureTitle';
import ResponsiveView from '../../common/components/ResponsiveView';
import CiteModalActionContainer from '../containers/CiteModalActionContainer';
import IncomingLiteratureReferencesLinkAction from '../../common/components/IncomingLiteratureReferencesLinkAction';
import ConferenceInfoList from './ConferenceInfoList';
import { getPapersQueryString } from '../utils';
import {
  InlineUL,
  SEPARATOR_MIDDLEDOT,
} from '../../common/components/InlineList';
import AssignViewContext from '../../authors/AssignViewContext';
import AssignOneActionContainer from '../../authors/containers/AssignOneActionContainer';

function LiteratureItem({ metadata, searchRank }) {
  const title = metadata.getIn(['titles', 0]);
  const authors = metadata.get('authors');

  const fullTextLinks = metadata.get('fulltext_links');
  const urls = metadata.get('urls');
  const dois = metadata.get('dois');
  const recordId = metadata.get('control_number');
  const citationCount = metadata.get('citation_count', 0);
  const authorCount = metadata.get('number_of_authors');
  const conferenceInfo = metadata.get('conference_info');

  const date = metadata.get('date');
  const publicationInfo = metadata.get('publication_info');
  const eprints = metadata.get('arxiv_eprints');
  const collaborations = metadata.get('collaborations');
  const collaborationsWithSuffix = metadata.get('collaborations_with_suffix');
  const canEdit = metadata.get('can_edit', false);

  const curatedRelation = metadata.get('curated_relation', false);

  const assignView = useContext(AssignViewContext);

  return (
    <ResultItem
      leftActions={
        <Fragment>
          {fullTextLinks && (
            <UrlsAction
              urls={fullTextLinks}
              icon={<FilePdfOutlined />}
              text="pdf"
              trackerEventId="PdfDownload"
            />
          )}
          {urls && (
            <UrlsAction
              urls={urls}
              text="links"
              trackerEventId="LiteratureFileLink"
            />
          )}
          {dois && <DOILinkAction dois={dois} />}
          <CiteModalActionContainer recordId={recordId} />
          {canEdit && (
            <EditRecordAction pidType="literature" pidValue={recordId} />
          )}
          {assignView && <AssignOneActionContainer recordId={recordId} />}
        </Fragment>
      }
      rightActions={
        <Fragment>
          {citationCount != null && (
            <IncomingLiteratureReferencesLinkAction
              linkQuery={getPapersQueryString(recordId)}
              referenceType="citation"
              itemCount={citationCount}
              trackerEventId="Citations:Search"
            />
          )}
        </Fragment>
      }
    >
      <div data-test-id="literature-result-item">
        <div className="flex flex-nowrap">
          <div className="flex-grow-1">
            <Link
              data-test-id="literature-result-title-link"
              className="result-item-title"
              to={`${LITERATURE}/${recordId}`}
            >
              <LiteratureTitle title={title} />
              {assignView &&
                !curatedRelation && <FileExclamationTwoTone className="ml1" />}
            </Link>
          </div>
          <ResponsiveView
            min="sm"
            render={() => <div className="light-silver pl2">#{searchRank}</div>}
          />
        </div>
        <div className="mt1">
          <AuthorsAndCollaborations
            authorCount={authorCount}
            authors={authors}
            collaborations={collaborations}
            collaborationsWithSuffix={collaborationsWithSuffix}
          />
          {date && (
            <>
              {' ('}
              <LiteratureDate date={date} />)
            </>
          )}
        </div>
        <div className="mt1">
          <InlineUL separator={SEPARATOR_MIDDLEDOT}>
            {publicationInfo && (
              <PublicationInfoList publicationInfo={publicationInfo} />
            )}
            {conferenceInfo && (
              <ConferenceInfoList conferenceInfo={conferenceInfo} />
            )}
            {eprints && <ArxivEprintList eprints={eprints} />}
          </InlineUL>
        </div>
      </div>
    </ResultItem>
  );
}

LiteratureItem.propTypes = {
  metadata: PropTypes.instanceOf(Map).isRequired,
  searchRank: PropTypes.number.isRequired,
};

export default LiteratureItem;

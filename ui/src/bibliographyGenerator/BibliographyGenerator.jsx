import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Row, Col, Upload, Button, Form, Alert } from 'antd';
import { Map, List } from 'immutable';
import { InboxOutlined } from '@ant-design/icons';
import CollapsableForm from '../submissions/common/components/CollapsableForm';
import SelectBox from '../common/components/SelectBox';

import './BibliographyGenerator.scss';
import ErrorAlert from '../common/components/ErrorAlert';
import DocumentHead from '../common/components/DocumentHead';

const { Dragger } = Upload;

const BIBLIOGRAPHY_GENERATOR_FORMATS = [
  { value: 'bibtex', display: 'BibTeX' },
  { value: 'latex_us', display: 'LaTeX (US)' },
  { value: 'latex_eu', display: 'LaTeX (EU)' },
];
const META_DESCRIPTION = 'Generate a list of references from a LaTeX file';
const TITLE = 'Bibliography Generator';

function BibliographyGenerator({
  onSubmit,
  loading,
  data,
  citationErrors,
  error,
}) {
  const [fileList, setFileList] = useState();

  const uploadProps = {
    onRemove: () => {
      setFileList(null);
    },
    beforeUpload: f => {
      setFileList([f]);
      return false;
    },
  };

  useEffect(
    () => {
      if (data) {
        window.open(data.get('download_url'), '_self');
      }
    },
    [data]
  );

  return (
    <>
      <DocumentHead title={TITLE} description={META_DESCRIPTION} />
      <Row type="flex" justify="center" className="overflow-x-auto">
        <Col className="mt3 mb3" xs={24} md={21} lg={16} xl={15} xxl={14}>
          <Row className="mb3 pa3 bg-white">
            <Col>
              <h2>Bibliography generator</h2>
              <p>
                <strong>
                  Want to use INSPIRE to generate you LaTeX/BibTeX bibliography?
                </strong>
              </p>
              <p>
                You can upload a LaTeX file here to generate a list of the
                references in the order they are cited in your paper. Just
                follow the three steps below and you will receive a bibliography
                ready to insert at the bottom of your LaTeX file with all the
                references properly ordered and formatted.
              </p>
            </Col>
          </Row>
          <Form
            name="bibliography-generator-form"
            onFinish={onSubmit}
            initialValues={{
              format: BIBLIOGRAPHY_GENERATOR_FORMATS[0].value,
            }}
          >
            <Row>
              <Col>
                <CollapsableForm>
                  <CollapsableForm.Section header="Example" key="example">
                    <p>
                      <strong>
                        Here is an example of a LaTeX file that could be sent to
                        our bibliography service, the output as LaTeX is shown
                        below.
                      </strong>
                    </p>
                    <pre className="latex-example">
                      {`
\\documentclass[12pt]{article}

\\begin {document}
\\begin{flushright}
{\\small
SLAC--PUB--10812\\\\
October 2012\\\\}
\\end{flushright}
                                                                              
\\title{A Really Great Paper with Excellent Bibliography}
\\author{Jane Q. Physicist \\\\
Stanford Linear Accelerator Center \\\\
Stanford University, Stanford, California 94309 \\\\
}

\\maketitle

This paper is pretty eclectic, since it cites a buch of diverse
  things.  Of course, since it has no content, that is perhaps not so
  difficult.

Primarily I want to refer the reader to Brodsky and Wu's recent work on the renormalization 
group\\cite{Brodsky:2012ms}, which is relatively unrelated to the recent
work by Beacom, Bell, and Dodelson \\cite{Beacom:2004yd}.  I should also point out that
the paper by Kreitz and Brooks \\cite{physics/0309027} is being cited here in a
purely self-serving manner.  

There are many papers by Dixon and others that I'd like to point out here
\\cite{hep-th/0501240,hep-th/0412210,JHEP.0412.015}. 
In particular I wish to point out that the work done in
\\cite{JHEP.0412.015} is irrelevant to this paper.  

There are some items in the paper \\cite{Akimov:2012vv} which I would like
to draw your attention to, but it is likely that as above, I may be citing
this for the wrong reasons.


I had better cite the most recent Review of Particle Properties
\\cite{Nakamura:2010zzi}, since that
gets quite a lot of cites, while citing a few papers about stringy topics
\\cite{hep-th/9711200} is also worthwhile.  No paper is complete without a cite to
some extra-dimensional papers like \\cite{hep-ph/9803315,hep-ph/9905221}.
Finally, let me make a mistake citing this paper \\cite{hep-scifi/0101001}.

\\begin{thebibliography}{99}


\\end{thebibliography}


\\end{document}
                    `}
                    </pre>

                    <p>
                      <strong>This will return:</strong>
                    </p>
                    <pre className="latex-example">
                      {`
%\\cite{Brodsky:2012ms}
\\bibitem{Brodsky:2012ms} 
  S.~J.~Brodsky and X.~-G.~Wu,
  %\`\`Self-Consistency Requirements of the Renormalization Group for Setting the Renormalization Scale,''
  Phys.\\ Rev.\\ D {\\bf 86}, 054018 (2012)
  [arXiv:1208.0700 [hep-ph]].
  %%CITATION = ARXIV:1208.0700;%%


%\\cite{Beacom:2004yd}
\\bibitem{Beacom:2004yd} 
  J.~F.~Beacom, N.~F.~Bell and S.~Dodelson,
  %\`\`Neutrinoless universe,''
  Phys.\\ Rev.\\ Lett.\\  {\\bf 93}, 121302 (2004)
  [astro-ph/0404585].
  %%CITATION = ASTRO-PH/0404585;%%


%\\cite{physics/0309027}
\\bibitem{physics/0309027} 
  P.~A.~Kreitz and T.~C.~Brooks,
  %\`\`Subject access through community partnerships: A Case study,''
  Sci.\\ Tech.\\ Libraries {\\bf 24}, 153 (2003)
  [physics/0309027 [physics.hist-ph]].
  %%CITATION = PHYSICS/0309027;%%


%\\cite{hep-th/0501240}
\\bibitem{hep-th/0501240} 
  Z.~Bern, L.~J.~Dixon and D.~A.~Kosower,
  %\`\`On-shell recurrence relations for one-loop QCD amplitudes,''
  Phys.\\ Rev.\\ D {\\bf 71}, 105013 (2005)
  [hep-th/0501240].
  %%CITATION = HEP-TH/0501240;%%


%\\cite{hep-th/0412210}
\\bibitem{hep-th/0412210} 
  Z.~Bern, L.~J.~Dixon and D.~A.~Kosower,
  %\`\`All Next-to-maximally-helicity-violating one-loop gluon amplitudes in N=4 super-Yang-Mills theory,''
  Phys.\\ Rev.\\ D {\\bf 72}, 045014 (2005)
  [hep-th/0412210].
  %%CITATION = HEP-TH/0412210;%%


%\\cite{JHEP.0412.015}
\\bibitem{JHEP.0412.015} 
  L.~J.~Dixon, E.~W.~N.~Glover and V.~V.~Khoze,
  %\`\`MHV rules for Higgs plus multi-gluon amplitudes,''
  JHEP {\\bf 0412}, 015 (2004)
  [hep-th/0411092].
  %%CITATION = HEP-TH/0411092;%%


%\\cite{Akimov:2012vv}
\\bibitem{Akimov:2012vv} 
  D.~Akimov {\\it et al.}  [DarkSide Collaboration],
  %\`\`Light Yield in DarkSide-10: a Prototype Two-phase Liquid Argon TPC for Dark Matter Searches,''
  arXiv:1204.6218 [astro-ph.IM].
  %%CITATION = ARXIV:1204.6218;%%


%\\cite{Nakamura:2010zzi}
\\bibitem{Nakamura:2010zzi} 
  K.~Nakamura {\\it et al.}  [Particle Data Group Collaboration],
  %\`\`Review of particle physics,''
  J.\\ Phys.\\ G {\\bf 37}, 075021 (2010).


%\\cite{hep-th/9711200}
\\bibitem{hep-th/9711200} 
  J.~M.~Maldacena,
  %\`\`The Large N limit of superconformal field theories and supergravity,''
  Adv.\\ Theor.\\ Math.\\ Phys.\\  {\\bf 2}, 231 (1998)
  [hep-th/9711200].
  %%CITATION = HEP-TH/9711200;%%


%\\cite{hep-ph/9803315}
\\bibitem{hep-ph/9803315} 
  N.~Arkani-Hamed, S.~Dimopoulos and G.~R.~Dvali,
  %\`\`The Hierarchy problem and new dimensions at a millimeter,''
  Phys.\\ Lett.\\ B {\\bf 429}, 263 (1998)
  [hep-ph/9803315].
  %%CITATION = HEP-PH/9803315;%%


%\\cite{hep-ph/9905221}
\\bibitem{hep-ph/9905221} 
  L.~Randall and R.~Sundrum,
  %\`\`A Large mass hierarchy from a small extra dimension,''
  Phys.\\ Rev.\\ Lett.\\  {\\bf 83}, 3370 (1999)
  [hep-ph/9905221].
  %%CITATION = HEP-PH/9905221;%%
                    `}
                    </pre>
                  </CollapsableForm.Section>
                </CollapsableForm>

                <Row className="pa3 bg-white">
                  <Col>
                    <Row className="mb3">
                      <Col>
                        <h3>Instructions</h3>
                        <p>
                          Write your paper in LaTeX as usual. Cite papers in
                          your LaTeX file in the following way:
                        </p>
                        <ol>
                          <li
                          >{`INSPIRE Texkeys, e.g. \\cite{Beacom:2010kk}`}</li>
                          <li
                          >{`Eprint numbers, e.g. \\cite{1004.3311} or \\cite{hep-th/9711200}`}</li>
                        </ol>
                        <p
                        >{`You can then upload your LaTeX file here to generate a list of the references in the order they are cited in your paper. The system will understand cite fields with multiple papers such as \\cite{Beacom:2010kk, hep-th/9711200}. Note that if you combine multiple papers under a single texkey only the one belonging to the texkey will show up, the others will not.`}</p>
                        <p>You have several options for the bibkey:</p>
                        <ol>
                          <li>hep-th/0001001 or any eprint number</li>
                          <li>
                            PhysRev.D66.010001 or any journal reference using
                            typical abbreviations for the journal name (note no
                            periods in the journal name)
                          </li>
                          <li>
                            Hagiwara:2002fs or any INSPIRE LaTeX key for the
                            paper
                          </li>
                        </ol>
                        <p>
                          You may also want to remember the following tips when
                          citing papers:
                        </p>
                        <ol>
                          <li
                          >{`You can combine multiple references in one \\cite command, again using commas to separate the references. Example: \\cite{Hagiwara:2002fs,hep-ex/0101001,PhysRev.D13.1}. These will be cited separately in your bibliography.`}</li>
                          <li>
                            The reference will always appear in the same format
                            regardless of how you cite it so if you have a
                            choice, use the eprint number as the identifier
                            rather than a journal publication note.
                          </li>
                          <li>
                            Do not worry about whether you have cited something
                            before, INSPIRE will get the order right based on
                            when you cited the references in the paper.
                          </li>
                          <li
                          >{`The only allowed characters in \\cite commands are letters, numbers and the following signs: "-", "/", ":", "," and ".". If your alias or bibkey contains something else, it will not be processed.`}</li>
                        </ol>
                        <p>
                          {`Output format: You can select "LaTeX (EU)" to create references in the European style (year before page). If you'd like the output in BiBTeX format, suitable for adding to your .bib file try generate bibtex, but beware that aliases to multiple articles (i.e., a nickname for many papers, cited as one) don't really work, since the .bib file expects separate entries for each paper. Note that this will generate BiBTeX output for the citations in you paper. You can't send a .bib file and get results this way.`}
                        </p>
                      </Col>
                    </Row>
                    <Row>
                      <Col span={24}>
                        <Form.Item
                          name="fileupload"
                          rules={[
                            {
                              required: true,
                              message: 'Please select a file',
                            },
                          ]}
                        >
                          <Dragger
                            {...uploadProps}
                            accept=".tex"
                            name="file"
                            fileList={fileList}
                          >
                            <p className="ant-upload-drag-icon">
                              <InboxOutlined />
                            </p>
                            <p className="ant-upload-text">LaTeX file</p>
                            <p className="ant-upload-hint">
                              Click or drag file to this area to upload
                            </p>
                          </Dragger>
                        </Form.Item>
                        <Form.Item label="Output format" name="format">
                          <SelectBox options={BIBLIOGRAPHY_GENERATOR_FORMATS} />
                        </Form.Item>
                      </Col>
                    </Row>
                    {citationErrors && (
                      <Row className="mb3">
                        <Col span={24}>
                          {citationErrors.map(e => (
                            <div className="mb2">
                              <Alert
                                type="warning"
                                message={e.get('message')}
                              />
                            </div>
                          ))}
                        </Col>
                      </Row>
                    )}
                    {error && (
                      <Row className="mb3">
                        <Col span={24}>
                          <ErrorAlert message={error.get('message')} />
                        </Col>
                      </Row>
                    )}
                    <Row type="flex" justify="end">
                      <Form.Item className="no-margin-bottom">
                        <Button
                          type="primary"
                          htmlType="submit"
                          disabled={!fileList}
                          loading={loading}
                        >
                          Submit
                        </Button>
                      </Form.Item>
                    </Row>
                  </Col>
                </Row>
              </Col>
            </Row>
          </Form>
        </Col>
      </Row>
    </>
  );
}

BibliographyGenerator.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
  data: PropTypes.instanceOf(Map),
  citationErrors: PropTypes.instanceOf(List),
  error: PropTypes.instanceOf(Map),
};

export default BibliographyGenerator;

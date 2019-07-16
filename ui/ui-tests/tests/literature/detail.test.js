const { routes } = require('../../utils/constants');
const { createPollyInstance } = require('../../utils/polly');
const {
  takeScreenShotForDesktop,
  takeScreenShotForMobile,
} = require('../../utils/screenshot');

describe('Literature Detail', () => {
  it('should match image snapshot for a literature', async () => {
    await page.setRequestInterception(true);
    const polly = createPollyInstance('LiteratureDetail');

    await page.goto(routes.public.literatureDetail1472986, {
      waitUntil: 'networkidle0',
    });

    const desktopSS = await takeScreenShotForDesktop(page);
    expect(desktopSS).toMatchImageSnapshot();

    const mobileSS = await takeScreenShotForMobile(page);
    expect(mobileSS).toMatchImageSnapshot();

    await polly.stop();
  });
});

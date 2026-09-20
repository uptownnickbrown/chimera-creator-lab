// Vendor prefixes for the real target device. Henry's iPad runs iPadOS 16.6
// (Railway request logs, 2026-09-20), whose Safari needs -webkit- for
// backdrop-filter (unprefixed only from Safari 18), user-select and
// text-size-adjust. Playwright's WebKit is far newer and never showed the
// difference: without this, six of the seven holo-panel blurs simply did
// not render on the iPad. Targets live in package.json "browserslist".
module.exports = { plugins: { autoprefixer: {} } };

const path = require('path');
const puppeteer = require('puppeteer');
const fs = require('fs');

const configPath = path.join(__dirname, '..', 'config.json');
if (!fs.existsSync(configPath)) process.exit(1);
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

const timestamp = () => new Date().toLocaleTimeString();

async function getLinks(server) {
    const linkDir = path.dirname(server.txtPath);
    if (!fs.existsSync(linkDir)) fs.mkdirSync(linkDir, { recursive: true });

    console.log(`\n[${timestamp()}] Starting task: ${server.name}`);

    const browser = await puppeteer.launch({
        headless: "new",
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1920, height: 1080 });

        page.on('console', msg => {
            if (msg.text().includes('[BROWSER]')) console.log(`  ↳ ${msg.text()}`);
        });

        if (config.settings?.userAgent) await page.setUserAgent(config.settings.userAgent);

        console.log(`[${timestamp()}] Navigating to: ${server.url}`);
        await page.goto(server.url, { waitUntil: 'networkidle2', timeout: 90000 });

        // Wait for content
        const primarySelector = server.selector.split(',')[0].trim();
        try {
            await page.waitForSelector(primarySelector, { timeout: 10000 });
        } catch (e) { /* ignore */ }

        console.log(`[${timestamp()}] Detecting scroll container...`);
        
        await page.evaluate(async () => {
            const log = (msg) => console.log(`[BROWSER] ${msg}`);

            function getContainer() {
                // 1. Try to find the specific app wrapper first
                const app = document.querySelector('#app');
                const list = document.querySelector('.wallpaper-list');
                const pic = document.querySelector('.pns-picture');
                
                // Prioritize checking if these specific elements are actually scrollable
                const candidates = [app, list, pic, document.documentElement];
                
                for (let el of candidates) {
                    if (!el) continue;
                    const style = window.getComputedStyle(el);
                    // Check if it has vertical overflow SET (auto/scroll) OR if it is the root
                    if (el === document.documentElement || style.overflowY === 'auto' || style.overflowY === 'scroll') {
                        if (el.scrollHeight > el.clientHeight) return el;
                    }
                }
                return document.documentElement; // Default fallback
            }

            let container = getContainer();
            let isWindowScroll = (container === document.documentElement || container === document.body);

            // Log initial state
            const getName = (el) => el.id ? `#${el.id}` : (el.className ? `.${el.className}` : el.tagName);
            log(`TARGET: ${getName(container)}`);
            log(`SIZE: ScrollHeight=${container.scrollHeight}, ClientHeight=${container.clientHeight}`);

            // --- SMART SCROLL LOOP ---
            await new Promise((resolve) => {
                let distance = 300;
                let retries = 0;
                let stuckCounter = 0;
                let lastScrollTop = -1;
                const maxRetries = 15; 

                const timer = setInterval(() => {
                    // 1. Get current position BEFORE scroll
                    let currentScrollTop = isWindowScroll ? window.scrollY : container.scrollTop;
                    const scrollHeight = isWindowScroll ? document.body.scrollHeight : container.scrollHeight;
                    const clientHeight = isWindowScroll ? window.innerHeight : container.clientHeight;

                    // 2. Perform Scroll
                    if (isWindowScroll) {
                        window.scrollBy(0, distance);
                    } else {
                        container.scrollBy(0, distance);
                    }

                    // 3. Get new position AFTER scroll attempt
                    let newScrollTop = isWindowScroll ? window.scrollY : container.scrollTop;

                    // --- STUCK PROTECTION ---
                    // If we tried to scroll but didn't move, and we aren't at the bottom yet
                    if (Math.abs(newScrollTop - lastScrollTop) < 1 && (newScrollTop + clientHeight) < (scrollHeight - 50)) {
                        stuckCounter++;
                        if (stuckCounter > 3) {
                            log(`⚠️ Stuck detected! Target element isn't scrolling.`);
                            if (!isWindowScroll) {
                                log(`🔄 Switching to WINDOW scroll fallback...`);
                                isWindowScroll = true; // Force switch to window
                                container = document.documentElement;
                                stuckCounter = 0;
                            } else {
                                log(`❌ Window also stuck. Forcing finish.`);
                                clearInterval(timer);
                                resolve();
                            }
                        }
                    } else {
                        stuckCounter = 0; // Reset if we moved
                    }
                    lastScrollTop = newScrollTop;

                    // 4. Check for bottom / Lazy Load
                    if ((newScrollTop + clientHeight) >= (scrollHeight - 50)) {
                        retries++;
                        if (retries % 5 === 0) log(`Waiting for content load... (${retries}/${maxRetries})`);
                        
                        // If scrollHeight increased, reset retries (content loaded!)
                        // Note: In next iteration, 'scrollHeight' variable will update
                        
                        if (retries >= maxRetries) {
                            log(`Finished scrolling.`);
                            clearInterval(timer);
                            resolve();
                        }
                    } else {
                        // If we are moving and not at bottom, reset finish retries
                        retries = 0; 
                    }
                }, 200);
            });
        });

        console.log(`[${timestamp()}] Extracting links...`);
        
        const links = await page.evaluate((selector) => {
            return Array.from(document.querySelectorAll(selector))
                .map(img => img.src)
                .filter(src => src && src.startsWith('http') && !src.includes('base64'))
                .map(url => {
                    try { return encodeURI(decodeURI(url.replace(/\+/g, '%20'))); } 
                    catch (e) { return url; }
                });
        }, server.selector);

        const uniqueLinks = [...new Set(links)];

        if (uniqueLinks.length > 0) {
            fs.writeFileSync(server.txtPath, uniqueLinks.join('\n'));
            console.log(`[${timestamp()}] Success: Saved ${uniqueLinks.length} unique links to ${server.txtPath}`);
        } else {
            console.warn(`[${timestamp()}] Warning: No links found for ${server.name}`);
        }

    } catch (error) {
        console.error(`[${timestamp()}] Error [${server.id}]: ${error.message}`);
    } finally {
        await browser.close();
    }
}

(async () => {
    console.log("=== SCRAPER STARTED ===");
    for (const server of config.servers) {
        await getLinks(server);
    }
    console.log("\n=== ALL TASKS COMPLETED ===\n");
})();

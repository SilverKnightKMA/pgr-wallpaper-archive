const path = require('path');
const puppeteer = require('puppeteer');
const fs = require('fs');

const configPath = path.join(__dirname, '..', 'config.json');
if (!fs.existsSync(configPath)) {
    console.error(`Error: Config file not found at ${configPath}`);
    process.exit(1);
}
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

const timestamp = () => new Date().toLocaleTimeString();

async function getLinks(server) {
    const linkDir = path.dirname(server.txtPath);
    if (!fs.existsSync(linkDir)) fs.mkdirSync(linkDir, { recursive: true });

    console.log(`\n[${timestamp()}] 🚀 STARTING TASK: ${server.name}`);

    const browser = await puppeteer.launch({
        headless: "new",
        protocolTimeout: 0, // Disable timeout for long-running scripts
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1920, height: 1080 });

        // --- OPTIMIZATION 1: BLOCK IMAGE & CSS LOADING ---
        // We only need the URL string, we don't need to actually render the image.
        // This speeds up the process significantly.
        await page.setRequestInterception(true);
        page.on('request', (req) => {
            const resourceType = req.resourceType();
            if (['image', 'stylesheet', 'font', 'media'].includes(resourceType)) {
                req.abort();
            } else {
                req.continue();
            }
        });

        if (config.settings?.userAgent) {
            await page.setUserAgent(config.settings.userAgent);
        }

        console.log(`[${timestamp()}] Navigating to: ${server.url}`);
        // 'domcontentloaded' is faster than 'networkidle2' because we don't wait for images
        await page.goto(server.url, { waitUntil: 'domcontentloaded', timeout: 0 });

        // Wait for the first element to ensure DOM is ready
        const primarySelector = server.selector.split(',')[0].trim();
        try {
            await page.waitForSelector(primarySelector, { timeout: 10000 });
        } catch (e) { /* ignore timeout */ }

        console.log(`[${timestamp()}] ⚡ Turbo scrolling started...`);

        // --- OPTIMIZATION 2: AGGRESSIVE SCROLLING ---
        const links = await page.evaluate(async (selector) => {
            
            // Helper to find the scrollable container
            const getScroller = () => {
                const app = document.querySelector('#app');
                const list = document.querySelector('.wallpaper-list');
                // Return specific container if it exists and has content, else return document
                return (app && app.scrollHeight > app.clientHeight) ? app : 
                       (list && list.scrollHeight > list.clientHeight) ? list : 
                       document.documentElement;
            };

            return await new Promise((resolve) => {
                let previousCount = 0;
                let retries = 0;
                // Stop if no new content is found after ~3 seconds (15 checks * 200ms)
                const MAX_RETRIES = 15; 

                const timer = setInterval(() => {
                    const scroller = getScroller();
                    
                    // 1. Force scroll to bottom immediately (no smooth behavior)
                    if (scroller) scroller.scrollTop = scroller.scrollHeight;
                    window.scrollTo(0, document.body.scrollHeight);

                    // 2. Count current image elements in DOM
                    const currentCount = document.querySelectorAll(selector).length;

                    if (currentCount > previousCount) {
                        // Content increased -> Reset retries
                        previousCount = currentCount;
                        retries = 0;
                    } else {
                        // Content didn't increase
                        retries++;
                        
                        if (retries >= MAX_RETRIES) {
                            clearInterval(timer);
                            
                            // 3. Extract Links
                            const imgs = document.querySelectorAll(selector);
                            const result = Array.from(imgs)
                                .map(img => img.src || img.getAttribute('data-src')) // Fallback to lazy-load attribute
                                .filter(src => src && src.startsWith('http') && !src.includes('base64'))
                                .map(url => {
                                    try { return encodeURI(decodeURI(url.replace(/\+/g, '%20'))); } 
                                    catch (e) { return url; }
                                });
                            resolve(result);
                        }
                    }
                }, 200); // Check every 200ms
            });

        }, server.selector);

        // --- SAVE RESULTS ---
        const uniqueLinks = [...new Set(links)];

        if (uniqueLinks.length > 0) {
            fs.writeFileSync(server.txtPath, uniqueLinks.join('\n'));
            console.log(`[${timestamp()}] ✅ Success: Found ${uniqueLinks.length} unique links. Saved to ${server.txtPath}`);
        } else {
            console.warn(`[${timestamp()}] ⚠️ Warning: No links found for ${server.name}`);
        }

    } catch (error) {
        console.error(`[${timestamp()}] ❌ Error [${server.id}]: ${error.message}`);
    } finally {
        await browser.close();
    }
}

(async () => {
    console.log("=== SCRAPER STARTED (TURBO MODE) ===");
    for (const server of config.servers) {
        await getLinks(server);
    }
    console.log("\n=== ALL TASKS COMPLETED ===\n");
})();

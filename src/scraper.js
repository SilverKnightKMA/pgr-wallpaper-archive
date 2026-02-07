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

        // Enable Browser Logs
        page.on('console', msg => {
            if (msg.text().includes('[BROWSER]')) console.log(`  ↳ ${msg.text()}`);
        });

        if (config.settings?.userAgent) await page.setUserAgent(config.settings.userAgent);

        console.log(`[${timestamp()}] Navigating to: ${server.url}`);
        await page.goto(server.url, { waitUntil: 'networkidle2', timeout: 90000 });

        // --- CRITICAL FIX 1: WAIT FOR ACTUAL IMAGES TO LOAD ---
        // We take the first selector from the config string to wait for
        const primarySelector = server.selector.split(',')[0].trim();
        console.log(`[${timestamp()}] Waiting for selector: "${primarySelector}"...`);
        
        try {
            await page.waitForSelector(primarySelector, { timeout: 15000 });
            console.log(`[${timestamp()}] Content loaded.`);
        } catch (e) {
            console.warn(`[${timestamp()}] Warning: Timeout waiting for selector. Page might be empty or slow.`);
        }

        console.log(`[${timestamp()}] Detecting scroll container...`);
        
        await page.evaluate(async () => {
            const log = (msg) => console.log(`[BROWSER] ${msg}`);

            // --- CRITICAL FIX 2: IMPROVED CONTAINER DETECTION ---
            function getContainer() {
                // 1. Define candidates
                const candidates = [
                    document.querySelector('.wallpaper-list'),
                    document.querySelector('.pns-picture'),
                    document.querySelector('#app'),
                    document.querySelector('main'),
                    document.documentElement // html
                ];

                // 2. Filter candidates that exist AND have actual scrollable content
                for (let el of candidates) {
                    if (!el) continue;
                    
                    const style = window.getComputedStyle(el);
                    const overflowY = style.overflowY;
                    const isScrollable = overflowY !== 'hidden' && overflowY !== 'visible';
                    const hasContent = el.scrollHeight > el.clientHeight;
                    
                    // If element has content larger than view, and isn't hidden, use it.
                    // Special case: #app might have overflow: hidden but contain the scroll, 
                    // so we mainly check dimensions.
                    if (el.scrollHeight > 0 && el.scrollHeight > el.clientHeight) {
                        return el;
                    }
                }

                // 3. Fallback: If no specific container found, return NULL to indicate Window scroll
                return null;
            }

            const container = getContainer();
            const isWindowScroll = !container || container === document.documentElement;
            
            if (isWindowScroll) {
                log(`TARGET: WINDOW (Fallback)`);
                log(`SIZE: DocumentHeight=${document.body.scrollHeight}`);
            } else {
                const name = container.id ? `#${container.id}` : container.className;
                log(`TARGET: ${name}`);
                log(`SIZE: ScrollHeight=${container.scrollHeight}, ClientHeight=${container.clientHeight}`);
            }

            // --- SCROLL LOOP ---
            await new Promise((resolve) => {
                let totalHeight = 0;
                let distance = 300;
                let retries = 0;
                const maxRetries = 20; 

                const timer = setInterval(() => {
                    // Determine scroll height based on target
                    let scrollHeight, currentScroll, clientHeight;

                    if (isWindowScroll) {
                        scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        currentScroll = window.scrollY;
                        clientHeight = window.innerHeight;
                    } else {
                        scrollHeight = container.scrollHeight;
                        container.scrollBy(0, distance);
                        currentScroll = container.scrollTop;
                        clientHeight = container.clientHeight;
                    }
                    
                    // Check if we hit bottom (with 50px buffer)
                    if ((currentScroll + clientHeight) >= (scrollHeight - 50)) {
                        retries++;
                        if (retries % 5 === 0) log(`Waiting for lazy load... (${retries}/${maxRetries})`);
                        
                        // If we are stuck at bottom for too long, finish.
                        if (retries >= maxRetries) {
                            log(`Finished scrolling.`);
                            clearInterval(timer);
                            resolve();
                        }
                    } else {
                        // Reset retries if height increased or we moved
                        retries = 0;
                        totalHeight += distance;
                    }
                }, 200);
            });
        });

        console.log(`[${timestamp()}] Extracting links...`);
        
        const links = await page.evaluate((selector) => {
            // Fix: ensure we select everything
            const imgs = document.querySelectorAll(selector);
            return Array.from(imgs)
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

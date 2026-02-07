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

        // Wait for the specific container to be present in DOM
        try {
            await page.waitForSelector('#app', { timeout: 5000 });
        } catch (e) { /* ignore if #app not found */ }

        console.log(`[${timestamp()}] detecting scroll container...`);
        
        await page.evaluate(async () => {
            const log = (msg) => console.log(`[BROWSER] ${msg}`);

            function getContainer() {
                // FORCE PRIORITY: Check for known wrapper IDs/Classes first.
                // We return these IMMEDIATELY without checking scrollHeight conditions
                // because sometimes the content loads slightly after.
                
                const app = document.querySelector('#app');
                if (app) return app;

                const wrapper = document.querySelector('.wallpaper-list') || 
                                document.querySelector('.pns-picture');
                if (wrapper) return wrapper;

                // Fallback: Find largest scrollable div
                const allDivs = Array.from(document.querySelectorAll('div'));
                const scrollables = allDivs.filter(el => {
                    const style = window.getComputedStyle(el);
                    return (style.overflowY === 'auto' || style.overflowY === 'scroll') 
                           && el.scrollHeight > el.clientHeight;
                });

                if (scrollables.length > 0) {
                    return scrollables.sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
                }

                return document.documentElement;
            }

            const container = getContainer();
            const containerName = container.id ? `#${container.id}` : (container.className ? `.${container.className}` : container.tagName);
            
            log(`TARGET CONTAINER: ${containerName}`);
            log(`INIT SIZE: ScrollHeight=${container.scrollHeight}, ClientHeight=${container.clientHeight}`);

            // --- SCROLL LOOP ---
            await new Promise((resolve) => {
                let totalHeight = 0;
                let distance = 300;
                let retries = 0;
                const maxRetries = 15; // Increased retries for slow loads

                const timer = setInterval(() => {
                    const scrollHeight = container.scrollHeight;
                    
                    // Force scroll logic
                    if (container === document.documentElement) {
                        window.scrollBy(0, distance);
                    } else {
                        container.scrollBy(0, distance);
                    }
                    
                    // Calculate current position
                    const scrollTop = (container === document.documentElement) ? window.scrollY : container.scrollTop;
                    const clientHeight = (container === document.documentElement) ? window.innerHeight : container.clientHeight;
                    
                    // Check if we hit bottom
                    if ((scrollTop + clientHeight) >= (scrollHeight - 100)) {
                        retries++;
                        if (retries % 5 === 0) log(`Waiting for lazy load... (${retries}/${maxRetries})`);
                        
                        if (retries >= maxRetries) {
                            log(`Finished scrolling.`);
                            clearInterval(timer);
                            resolve();
                        }
                    } else {
                        retries = 0;
                        totalHeight += distance;
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

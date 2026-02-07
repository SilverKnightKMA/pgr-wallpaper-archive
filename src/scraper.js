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
    if (!fs.existsSync(linkDir)) {
        fs.mkdirSync(linkDir, { recursive: true });
    }

    console.log(`\n[${timestamp()}] Starting task: ${server.name}`);

    const browser = await puppeteer.launch({
        headless: "new",
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1920, height: 1080 });

        // --- DEBUG: ENABLE CONSOLE LOG FROM BROWSER ---
        page.on('console', msg => {
            const type = msg.type();
            // Chỉ hiện log tay của mình (bắt đầu bằng [BROWSER]) để đỡ rối
            if (msg.text().includes('[BROWSER]')) {
                console.log(`  ↳ ${msg.text()}`);
            }
        });

        if (config.settings && config.settings.userAgent) {
            await page.setUserAgent(config.settings.userAgent);
        }

        console.log(`[${timestamp()}] Navigating to: ${server.url}`);
        await page.goto(server.url, { waitUntil: 'networkidle2', timeout: 90000 });

        console.log(`[${timestamp()}] detecting scroll container...`);
        
        await page.evaluate(async () => {
            // Helper log function
            const log = (msg) => console.log(`[BROWSER] ${msg}`);

            function getContainer() {
                // 1. Try generic scroll check first (Most reliable)
                // Find ALL divs, sort by scrollHeight descending to find the biggest scrollable area
                const allDivs = Array.from(document.querySelectorAll('div, ul, section, main'));
                
                // Find elements that have scrollable overflow AND content larger than view
                const scrollables = allDivs.filter(el => {
                    const style = window.getComputedStyle(el);
                    const isScrollable = style.overflowY === 'auto' || style.overflowY === 'scroll';
                    const hasOverflow = el.scrollHeight > el.clientHeight;
                    return isScrollable && hasOverflow;
                });

                if (scrollables.length > 0) {
                    // Return the one with the largest scrollHeight (likely the main wrapper)
                    return scrollables.sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
                }

                // 2. Fallback to specific selectors if generic fails
                let node = document.querySelector('.wallpaper-list') || 
                           document.querySelector('#app');
                
                if (node && node.scrollHeight > node.clientHeight) return node;

                // 3. Last resort
                return document.documentElement;
            }

            const container = getContainer();
            
            // --- DEBUG INFO ---
            const containerName = container.id ? `#${container.id}` : 
                                  container.className ? `.${container.className}` : 
                                  container.tagName;
            
            log(`TARGET CONTAINER: ${containerName}`);
            log(`START DIMENSIONS: ScrollHeight=${container.scrollHeight}, ClientHeight=${container.clientHeight}`);
            
            if (container.scrollHeight <= container.clientHeight) {
                log(`WARNING: Container does not seem scrollable! (Scroll <= Client)`);
            }

            // --- SCROLL LOGIC (INCREMENTAL) ---
            await new Promise((resolve) => {
                let totalHeight = 0;
                let distance = 300; // Scroll distance per step
                let retries = 0;
                const maxRetries = 10; // More retries for safety

                const timer = setInterval(() => {
                    const scrollHeight = container.scrollHeight;
                    
                    // Use scrollBy for smoother lazy load triggering
                    // If container is documentElement/body, use window.scrollBy
                    if (container === document.documentElement || container === document.body) {
                        window.scrollBy(0, distance);
                    } else {
                        container.scrollBy(0, distance);
                    }
                    
                    // Check if we reached bottom
                    const currentScroll = (container === document.documentElement) ? window.scrollY : container.scrollTop;
                    const viewHeight = (container === document.documentElement) ? window.innerHeight : container.clientHeight;

                    // Log progress every 5 ticks to avoid spam
                    if (totalHeight % (distance * 5) === 0) {
                        log(`Scrolling... Current: ${Math.floor(currentScroll + viewHeight)} / ${scrollHeight}`);
                    }

                    if ((currentScroll + viewHeight) >= (scrollHeight - 50)) {
                        retries++;
                        if (retries >= maxRetries) {
                            log(`Reached bottom. Finished.`);
                            clearInterval(timer);
                            resolve();
                        }
                    } else {
                        retries = 0; // Reset retries if we are still moving
                        totalHeight += distance;
                    }
                }, 200); // 200ms delay between scrolls
            });
        });

        console.log(`[${timestamp()}] Extracting links...`);
        
        const links = await page.evaluate((selector) => {
            const imgs = document.querySelectorAll(selector);
            return Array.from(imgs)
                .map(img => img.src)
                .filter(src => src && src.startsWith('http') && !src.includes('base64'))
                .map(url => {
                    try {
                        let fixed = url.replace(/\+/g, '%20');
                        return encodeURI(decodeURI(fixed));
                    } catch (e) { return url; }
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

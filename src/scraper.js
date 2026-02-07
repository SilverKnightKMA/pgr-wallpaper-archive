const path = require('path');
const puppeteer = require('puppeteer');
const fs = require('fs');

// Load configuration
const configPath = path.join(__dirname, '..', 'config.json');
if (!fs.existsSync(configPath)) {
    console.error(`Error: Config file not found at ${configPath}`);
    process.exit(1);
}
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

// Helper for logging time
const timestamp = () => new Date().toLocaleTimeString();

async function getLinks(server) {
    // Ensure output directory exists
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
        
        // Apply User-Agent from config
        if (config.settings && config.settings.userAgent) {
            await page.setUserAgent(config.settings.userAgent);
        }

        console.log(`[${timestamp()}] Navigating to: ${server.url}`);
        await page.goto(server.url, { waitUntil: 'networkidle2', timeout: 90000 });

        // --- SCROLL LOGIC ---
        // Identifies the scrollable container and scrolls to trigger lazy loading
        console.log(`[${timestamp()}] detecting scroll container and loading content...`);
        
        await page.evaluate(async () => {
            // Function to find the actual scrollable element (not always window/body)
            function getContainer() {
                // 1. Check for specific PGR site elements first
                let node = document.querySelector('.wallpaper-list') || 
                           document.querySelector('.pns-picture') || 
                           document.querySelector('.pcWallpaper')?.parentElement ||
                           document.querySelector('#app');
                
                if (node && node.scrollHeight > node.clientHeight) return node;

                // 2. Fallback: Find any div with vertical overflow
                for (let div of document.querySelectorAll('div')) {
                    let s = window.getComputedStyle(div);
                    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && div.scrollHeight > div.clientHeight) {
                        return div;
                    }
                }
                
                // 3. Default to document element
                return document.documentElement;
            }

            const container = getContainer();
            let lastHeight = container.scrollHeight;
            let retries = 0;
            const maxRetries = 5;

            // Scroll loop: keeps scrolling until height stops increasing
            while (retries < maxRetries) {
                container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
                
                // Wait for content to render (simulate 2s delay)
                await new Promise(r => setTimeout(r, 2000));
                
                let newHeight = container.scrollHeight;
                if (newHeight === lastHeight) {
                    retries++; // Height didn't change, increment retry counter
                } else {
                    lastHeight = newHeight;
                    retries = 0; // Content loaded, reset counter
                }
            }
        });

        // --- EXTRACTION LOGIC ---
        console.log(`[${timestamp()}] Extracting links...`);
        
        const links = await page.evaluate((selector) => {
            const imgs = document.querySelectorAll(selector);
            return Array.from(imgs)
                .map(img => img.src)
                .filter(src => src && src.startsWith('http') && !src.includes('base64'))
                .map(url => {
                    // Normalize URL encoding
                    try {
                        let fixed = url.replace(/\+/g, '%20');
                        return encodeURI(decodeURI(fixed));
                    } catch (e) { return url; }
                });
        }, server.selector);

        // Deduplicate links
        const uniqueLinks = [...new Set(links)];

        // Save to file
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

// Main execution loop
(async () => {
    console.log("=== SCRAPER STARTED ===");
    for (const server of config.servers) {
        await getLinks(server);
    }
    console.log("\n=== ALL TASKS COMPLETED ===\n");
})();

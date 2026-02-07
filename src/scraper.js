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
        protocolTimeout: 0, 
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1920, height: 1080 });
        
        page.setDefaultNavigationTimeout(0);
        page.setDefaultTimeout(0);

        page.on('console', msg => {
            if (msg.text().includes('[BROWSER]')) console.log(`  ↳ ${msg.text()}`);
        });

        if (config.settings?.userAgent) await page.setUserAgent(config.settings.userAgent);

        console.log(`[${timestamp()}] Navigating to: ${server.url}`);
        await page.goto(server.url, { waitUntil: 'networkidle2', timeout: 0 });

        // Wait for content
        const primarySelector = server.selector.split(',')[0].trim();
        try {
            await page.waitForSelector(primarySelector, { timeout: 15000 });
        } catch (e) { /* ignore */ }

        console.log(`[${timestamp()}] Injecting scrolling logic...`);

        const links = await page.evaluate(async (selector) => {
            const log = (msg) => console.log(`[BROWSER] ${msg}`);

            function getContainer() {
                let node = document.querySelector('.wallpaper-list') || 
                           document.querySelector('.pns-picture') || 
                           document.querySelector('.pcWallpaper')?.parentElement ||
                           document.querySelector('#app');
                
                if (node && node.scrollHeight > node.clientHeight) return node;

                for (let div of document.querySelectorAll('div')) {
                    let s = window.getComputedStyle(div);
                    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && div.scrollHeight > div.clientHeight) {
                        return div;
                    }
                }
                return document.documentElement;
            }

            const container = getContainer();
            const containerName = container.id ? `#${container.id}` : (container.className ? `.${container.className}` : container.tagName);
            
            log(`Target: ${containerName} (Height: ${container.scrollHeight})`);

            await new Promise((resolve) => {
                let lastHeight = container.scrollHeight;
                let retries = 0;
                const maxRetries = 10; 

                const timer = setInterval(() => {
                    if (container === document.documentElement) {
                        window.scrollTo(0, document.body.scrollHeight);
                    } else {
                        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
                    }

                    const newHeight = container.scrollHeight;
                    
                    if (newHeight === lastHeight) {
                        retries++;
                        if (retries % 2 === 0) log(`Waiting... (${retries}/${maxRetries})`);
                        
                        if (retries >= maxRetries) {
                            log("Finished scrolling.");
                            clearInterval(timer);
                            resolve();
                        }
                    } else {
                        log(`Height increased: ${newHeight}px`);
                        lastHeight = newHeight;
                        retries = 0;
                    }
                }, 800);
            });

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

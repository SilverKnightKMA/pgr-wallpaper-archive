const path = require('path');
const fs = require('fs');

const configPath = path.join(__dirname, '..', 'config.json');
if (!fs.existsSync(configPath)) {
    console.error(`Error: Config file not found at ${configPath}`);
    process.exit(1);
}
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

const timestamp = () => new Date().toLocaleTimeString();

// Function to dynamically import p-limit
async function getPLimit() {
    const { default: pLimit } = await import('p-limit');
    return pLimit;
}

// Function to list images in a directory
function listImagesInDirectory(directory) {
    if (!fs.existsSync(directory)) return [];
    return fs.readdirSync(directory).filter(file => file.endsWith('.jpg') || file.endsWith('.png'));
}

// Function to list all images across configured directories
function listAllImages(directories) {
    const allImages = new Set();
    for (const dir of directories) {
        const images = listImagesInDirectory(dir);
        images.forEach(image => allImages.add(image));
    }
    return allImages;
}

async function getLinks(server, maxImages, existingImages) {
    const linkDir = path.dirname(server.txtPath);
    if (!fs.existsSync(linkDir)) fs.mkdirSync(linkDir, { recursive: true });

    console.log(`\n[${timestamp()}] 🚀 STARTING TASK: ${server.name}`);

    const browser = await puppeteer.launch({
        headless: "new",
        protocolTimeout: 0,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1920, height: 1080 });

        // Enable log forwarding
        page.on('console', msg => {
            if (msg.text().includes('[BROWSER]')) console.log(`  ↳ ${msg.text()}`);
        });

        if (config.settings?.userAgent) {
            await page.setUserAgent(config.settings.userAgent);
        }

        console.log(`[${timestamp()}] Navigating to: ${server.url}`);
        await page.goto(server.url, { waitUntil: 'networkidle2', timeout: 0 });

        // Wait for primary selector
        const primarySelector = server.selector.split(',')[0].trim();
        console.log(`[${timestamp()}] Waiting for selector: "${primarySelector}"...`);
        try {
            await page.waitForSelector(primarySelector, { timeout: 20000 });
            console.log(`[${timestamp()}] Selector found. Page ready.`);
        } catch (e) {
            console.warn(`[${timestamp()}] ⚠️ Selector NOT found immediately. Continuing anyway...`);
        }

        console.log(`[${timestamp()}] 📜 Starting Smart Scroll Loop...`);

        const links = await page.evaluate(async (selector, maxImages, existingCount) => {
            const log = (msg) => console.log(`[BROWSER] ${msg}`);

            const getScroller = () => {
                const candidates = [
                    document.querySelector('#app'),
                    document.querySelector('.wallpaper-list'),
                    document.querySelector('.pns-picture'),
                    document.documentElement
                ];
                return candidates.filter(e => e).sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
            };

            const countImages = () => document.querySelectorAll(selector).length;

            return await new Promise(async (resolve) => {
                let previousCount = countImages();
                let retries = 0;
                let totalCount = existingCount;
                
                const MAX_RETRIES = 10; 
                const WAIT_TIME = 2000; 

                log(`Initial Image Count: ${previousCount}`);

                log(`Warm-up scroll...`);
                const scroller = getScroller();
                if (scroller) scroller.scrollBy(0, 500);
                window.scrollBy(0, 500);
                
                await new Promise(r => setTimeout(r, 4000));
                
                const timer = setInterval(() => {
                    const scroller = getScroller();
                    const distance = 1000;
                    
                    window.scrollBy(0, distance);
                    if (scroller && scroller !== document.documentElement) {
                        scroller.scrollBy(0, distance);
                        
                        if (scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 100) {
                             // Force bottom check
                             scroller.scrollTop = scroller.scrollHeight;
                        }
                    }

                    const currentCount = countImages();

                    if (currentCount > previousCount) {
                        log(`✅ NEW CONTENT: ${currentCount} images (was ${previousCount})`);
                        totalCount += (currentCount - previousCount);
                        previousCount = currentCount;
                        retries = 0; // Reset

                        if (totalCount >= maxImages) {
                            log(`🚨 Total images (${totalCount}) reached maxImages (${maxImages}). Stopping scroll.`);
                            clearInterval(timer);
                            const imgs = document.querySelectorAll(selector);
                            const result = Array.from(imgs)
                                .map(img => img.src)
                                .filter(src => src && src.startsWith('http') && !src.includes('base64'))
                                .map(url => {
                                    try { return encodeURI(decodeURI(url.replace(/\+/g, '%20'))); } 
                                    catch (e) { return url; }
                                });
                            resolve(result);
                        }
                    } else {
                        retries++;
                        log(`⏳ Waiting... (${retries}/${MAX_RETRIES}) - Count: ${currentCount}`);
                        
                        if (retries >= MAX_RETRIES) {
                            log(`🛑 Finished scrolling.`);
                            clearInterval(timer);
                            const imgs = document.querySelectorAll(selector);
                            const result = Array.from(imgs)
                                .map(img => img.src)
                                .filter(src => src && src.startsWith('http') && !src.includes('base64'))
                                .map(url => {
                                    try { return encodeURI(decodeURI(url.replace(/\+/g, '%20'))); } 
                                    catch (e) { return url; }
                                });
                            resolve(result);
                        }
                    }
                }, WAIT_TIME);
            });

        }, server.selector, maxImages, existingImages.size);

        // --- SAVE RESULTS ---
        const uniqueLinks = [...new Set(links)];
        const newLinks = uniqueLinks.filter(link => !existingImages.has(path.basename(link)));

        if (newLinks.length > 0) {
            fs.writeFileSync(server.txtPath, newLinks.join('\n'));
            console.log(`[${timestamp()}] ✅ Success: Found ${newLinks.length} new unique links. Saved to ${server.txtPath}`);
        } else {
            console.warn(`[${timestamp()}] ⚠️ Warning: No new links found for ${server.name}`);
        }

    } catch (error) {
        console.error(`[${timestamp()}] ❌ Error [${server.id}]: ${error.message}`);
    } finally {
        await browser.close();
    }
}

(async () => {
    const maxImages = parseInt(process.env.MAX_IMAGES, 10) || 1000; // Default to 1000 if not provided
    console.log(`=== SCRAPER STARTED (SMART SCROLL) ===`);
    console.log(`[${timestamp()}] Max images allowed: ${maxImages}`);

    // List existing images
    const directories = config.servers.map(server => server.imageDir);
    const existingImages = listAllImages(directories);
    console.log(`[${timestamp()}] 📂 Existing images: ${existingImages.size}`);

    const pLimit = await getPLimit();
    const limit = pLimit(4); // Limit concurrency to 4 threads

    await Promise.all(
        config.servers.map(server =>
            limit(() => getLinks(server, maxImages, existingImages))
        )
    );

    console.log(`\n=== ALL TASKS COMPLETED ===\n`);
})();

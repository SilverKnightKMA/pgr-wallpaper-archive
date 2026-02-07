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
        protocolTimeout: 0, 
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1920, height: 1080 });

        // --- 1. ENABLE CONSOLE LOGS (Quan trọng để debug) ---
        page.on('console', msg => {
            const text = msg.text();
            // Chỉ hiện log do mình viết (có prefix [BROWSER])
            if (text.includes('[BROWSER]')) {
                console.log(`  ↳ ${text}`);
            }
        });

        if (config.settings?.userAgent) {
            await page.setUserAgent(config.settings.userAgent);
        }

        console.log(`[${timestamp()}] Navigating to: ${server.url}`);
        // Dùng networkidle2 để đảm bảo trang load xong hoàn toàn
        await page.goto(server.url, { waitUntil: 'networkidle2', timeout: 0 });

        // Chờ selector đầu tiên
        const primarySelector = server.selector.split(',')[0].trim();
        console.log(`[${timestamp()}] Waiting for selector: "${primarySelector}"...`);
        try {
            await page.waitForSelector(primarySelector, { timeout: 20000 });
            console.log(`[${timestamp()}] Selector found. Page ready.`);
        } catch (e) {
            console.warn(`[${timestamp()}] ⚠️ Selector NOT found immediately. Page might be empty or slow.`);
        }

        console.log(`[${timestamp()}] 📜 Starting Scroll Loop...`);

        // --- 2. SCROLL LOGIC (Image Count Strategy) ---
        const links = await page.evaluate(async (selector) => {
            const log = (msg) => console.log(`[BROWSER] ${msg}`);

            // Hàm đếm số ảnh thực tế đang có trong DOM
            const countImages = () => document.querySelectorAll(selector).length;

            // Hàm tìm thằng cuộn to nhất (để scroll nó)
            const getScroller = () => {
                const candidates = [
                    document.querySelector('#app'),
                    document.querySelector('.wallpaper-list'),
                    document.querySelector('.pns-picture'),
                    document.documentElement
                ];
                return candidates.filter(e => e).sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
            };

            return await new Promise((resolve) => {
                let previousCount = countImages();
                let retries = 0;
                const MAX_RETRIES = 5; 
                const WAIT_TIME = 2000; // 2 giây chờ load

                log(`Initial Image Count: ${previousCount}`);

                const timer = setInterval(() => {
                    // 1. Scroll mạnh xuống đáy
                    const scroller = getScroller();
                    
                    // Scroll cả Window lẫn Container để chắc chắn trúng
                    window.scrollTo(0, document.body.scrollHeight);
                    if (scroller && scroller !== document.documentElement) {
                        scroller.scrollTop = scroller.scrollHeight;
                    }

                    // 2. Kiểm tra kết quả
                    const currentCount = countImages();

                    if (currentCount > previousCount) {
                        log(`✅ Loaded new images! Total: ${currentCount} (was ${previousCount})`);
                        previousCount = currentCount;
                        retries = 0; // Reset
                    } else {
                        retries++;
                        log(`⏳ No change... Waiting (${retries}/${MAX_RETRIES}) - Count: ${currentCount}`);
                        
                        if (retries >= MAX_RETRIES) {
                            log(`🛑 Finished scrolling.`);
                            clearInterval(timer);
                            
                            // 3. Trích xuất link
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
    console.log("=== SCRAPER STARTED (DEBUG MODE) ===");
    for (const server of config.servers) {
        await getLinks(server);
    }
    console.log("\n=== ALL TASKS COMPLETED ===\n");
})();

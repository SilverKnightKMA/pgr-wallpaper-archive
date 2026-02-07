#!/usr/bin/env node
/**
 * Test script to validate filename encoding consistency across the system
 * 
 * This tests:
 * 1. encodeFilename() function behavior
 * 2. Consistency between manifest and actual files
 * 3. URL encoding for special characters
 * 4. Edge cases with various Unicode characters
 */

const fs = require('fs');
const path = require('path');

// Import the actual encodeFilename function from generate_readme.js
// Note: generate_readme.js must export these functions for testing
try {
    const { encodeFilename } = require('../src/generate_readme.js');
    module.exports.encodeFilename = encodeFilename;
} catch (error) {
    console.error('❌ Failed to import encodeFilename from generate_readme.js');
    console.error('   Make sure generate_readme.js exports the function:');
    console.error('   module.exports = { encodeFilename, ... }');
    process.exit(1);
}

const { encodeFilename } = module.exports;

console.log('='.repeat(70));
console.log('Filename Encoding Test Suite');
console.log('='.repeat(70));

let passCount = 0;
let failCount = 0;

function test(name, condition, details = '') {
    if (condition) {
        console.log(`✅ PASS: ${name}`);
        if (details) console.log(`   ${details}`);
        passCount++;
    } else {
        console.log(`❌ FAIL: ${name}`);
        if (details) console.log(`   ${details}`);
        failCount++;
    }
}

// Test 1: Basic Chinese characters
console.log('\n📝 Test 1: Basic Chinese Character Encoding');
const test1Input = '英文.jpg';
const test1Output = encodeFilename(test1Input);
const test1Expected = '%E8%8B%B1%E6%96%87.jpg';
test(
    'Chinese characters are encoded',
    test1Output === test1Expected,
    `Input: "${test1Input}" → Output: "${test1Output}"`
);

// Test 2: Filename with Chinese in middle
console.log('\n📝 Test 2: Filename with Chinese Characters');
const test2Input = '0lh4t2cs5iogkak3vh-1766655448792英文.jpg';
const test2Output = encodeFilename(test2Input);
const test2Expected = '0lh4t2cs5iogkak3vh-1766655448792%E8%8B%B1%E6%96%87.jpg';
test(
    'Filename with Chinese is correctly encoded',
    test2Output === test2Expected,
    `Output: "${test2Output}"`
);

// Test 3: Already encoded filename (idempotency)
console.log('\n📝 Test 3: Idempotency (encoding already-encoded filename)');
const test3Input = '0lh4t2cs5iogkak3vh-1766655448792%E8%8B%B1%E6%96%87.jpg';
const test3Output = encodeFilename(test3Input);
const test3Expected = '0lh4t2cs5iogkak3vh-1766655448792%E8%8B%B1%E6%96%87.jpg';
test(
    'Already encoded filename remains unchanged',
    test3Output === test3Expected,
    `Input: "${test3Input}" → Output: "${test3Output}"`
);

// Test 4: Multiple encodings don't double-encode
console.log('\n📝 Test 4: Double Encoding Prevention');
const test4Input = '英文.jpg';
const test4Once = encodeFilename(test4Input);
const test4Twice = encodeFilename(test4Once);
test(
    'Double encoding is prevented (idempotent)',
    test4Once === test4Twice,
    `Once: "${test4Once}", Twice: "${test4Twice}"`
);

// Test 5: Special characters in path
console.log('\n📝 Test 5: Special Characters');
const test5Input = '渡边-他们所在01_.jpg';
const test5Output = encodeFilename(test5Input);
test(
    'Japanese characters and hyphens are handled',
    test5Output.includes('%') && test5Output.includes('-'),
    `Output: "${test5Output}"`
);

// Test 6: Spaces (should be encoded)
console.log('\n📝 Test 6: Space Encoding');
const test6Input = 'file name.jpg';
const test6Output = encodeFilename(test6Input);
test(
    'Spaces are encoded',
    test6Output === 'file%20name.jpg',
    `Output: "${test6Output}"`
);

// Test 7: Lone percent sign
console.log('\n📝 Test 7: Lone Percent Sign');
const test7Input = 'file%test.jpg';
const test7Output = encodeFilename(test7Input);
test(
    'Lone % is encoded to %25',
    test7Output === 'file%25test.jpg',
    `Output: "${test7Output}"`
);

// Test 8: Valid percent encoding is preserved
console.log('\n📝 Test 8: Valid Percent Encoding Preservation');
const test8Input = 'file%20test.jpg';
const test8Output = encodeFilename(test8Input);
test(
    'Valid %20 is preserved',
    test8Output === 'file%20test.jpg',
    `Output: "${test8Output}"`
);

// Test 9: Mixed valid and invalid percent
console.log('\n📝 Test 9: Mixed Percent Signs');
const test9Input = 'file%20and%test.jpg';
const test9Output = encodeFilename(test9Input);
test(
    'Valid %20 preserved, lone % encoded',
    test9Output === 'file%20and%25test.jpg',
    `Output: "${test9Output}"`
);

// Test 10: Load and validate manifest (if exists)
console.log('\n📝 Test 10: Manifest Validation');
const manifestPath = path.join(__dirname, '..', 'data', 'manifest.json');
if (fs.existsSync(manifestPath)) {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    const servers = Object.keys(manifest).filter(k => k !== 'releaseTime');
    
    let allFilenamesValid = true;
    let sampleFilename = '';
    let errorDetails = '';
    
    for (const serverId of servers) {
        if (manifest[serverId].wallpapers) {
            for (const wallpaper of manifest[serverId].wallpapers) {
                const fn = wallpaper.filename;
                // Check that filename doesn't contain URL-encoded %XX sequences
                // Note: decoded filenames can legitimately contain literal % characters
                if (fn && /%[0-9A-Fa-f]{2}/.test(fn)) {
                    try {
                        // Check if it's a valid encoding or not
                        const decoded = decodeURIComponent(fn);
                        if (decoded !== fn) {
                            allFilenamesValid = false;
                            sampleFilename = fn;
                            errorDetails = `Found URL-encoded filename in ${serverId}: "${fn}" (should be "${decoded}")`;
                            break;
                        }
                    } catch (e) {
                        // URIError from malformed percent encoding
                        allFilenamesValid = false;
                        errorDetails = `Malformed percent encoding in ${serverId}: "${fn}" (${e.message})`;
                        break;
                    }
                }
                if (!sampleFilename && fn) {
                    sampleFilename = fn;
                }
            }
        }
        if (!allFilenamesValid) break;
    }
    
    test(
        'Manifest stores decoded filenames (not URL-encoded)',
        allFilenamesValid,
        errorDetails || (sampleFilename ? `Sample valid filename: "${sampleFilename}"` : '')
    );
} else {
    console.log('⏭️  SKIP: Manifest file not found');
}

// Summary
console.log('\n' + '='.repeat(70));
console.log(`Test Summary: ${passCount} passed, ${failCount} failed`);
console.log('='.repeat(70));

process.exit(failCount > 0 ? 1 : 0);

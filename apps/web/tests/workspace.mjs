import assert from 'node:assert/strict'
import {randomUUID} from 'node:crypto'
import {readFile} from 'node:fs/promises'
import {chromium} from 'playwright-core'

// Run against the isolated rehearsal stack with a synthetic project.
const base = process.env.PUBLIC_BASE_URL || 'http://localhost:8080'
const browser = await chromium.launch({channel:'chrome', executablePath:process.env.CHROME_PATH || undefined})
try {
  const page = await browser.newPage({viewport:{width:1100,height:800}})
  const errors = []
  page.on('pageerror', err => errors.push(err.message))
  await page.goto(base)
  const password = (await readFile(new URL('../../../.secrets/owner_password', import.meta.url),'utf8')).trim()
  const field = page.getByLabel('Owner password')
  await field.fill('incorrect')
  await field.press('Enter')
  await page.getByRole('alert').filter({hasText:'Invalid credentials'}).waitFor()
  await field.fill(password)
  await field.press('Enter')
  await page.getByRole('button',{name:'+ New project',exact:true}).click()
  const title = 'Rehearsal '+randomUUID().slice(0,8)
  await page.getByLabel('New project',{exact:true}).fill(title)
  await page.getByRole('button',{name:'Create',exact:true}).click()
  await page.getByRole('button',{name:'+ New conversation',exact:true}).click()
  await page.getByLabel('New conversation',{exact:true}).fill('Planning')
  await page.getByRole('button',{name:'Create',exact:true}).click()
  await page.getByLabel('Question',{exact:true}).fill('Which constraint should we check first?')
  await page.getByLabel('Manual model names',{exact:false}).fill('A, B')
  await page.getByRole('button',{name:'Start comparison'}).click()
  // Select the first target in the ordered response list.
  await page.locator('details summary').first().click()
  await page.getByLabel('Original response').first().fill('Check the deployment region.\nPreserve this wording.')
  await page.getByRole('button',{name:'Save original'}).first().click()
  await page.getByText('Imported',{exact:true}).waitFor()
  await page.reload()
  await page.getByRole('heading',{name:'Planning',exact:true}).waitFor()
  await page.locator('details summary').first().click()
  assert.equal(await page.locator('details[open] .original').innerText(), 'Check the deployment region.\nPreserve this wording.')
  await page.setViewportSize({width:390,height:844})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth),true)
  await page.getByRole('button',{name:'Sign out'}).click()
  await page.getByLabel('Owner password').waitFor()
  assert.deepEqual(errors,[])
  console.log('Browser journey passed for '+title)
} finally {
  await browser.close()
}

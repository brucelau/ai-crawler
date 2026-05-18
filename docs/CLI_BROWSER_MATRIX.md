# CLI Browser Capability Matrix

All 5 backends support the full command set. Adapter details below.

## Capability Matrix

```
┌────────────┬───────────────────────┬──────────┬──────────────┬──────────────┬─────────────────────────┐
│    能力    │      playwright       │ camoufox │ cloakbrowser │ seleniumbase │ undetected_chromedriver │
├────────────┼───────────────────────┼──────────┼──────────────┼──────────────┼─────────────────────────┤
│ type/keys  │ ✅ 原生键盘API        │ ✅       │ ✅           │ ✅ 适配器    │ ✅ 适配器               │
├────────────┼───────────────────────┼──────────┼──────────────┼──────────────┼─────────────────────────┤
│ click      │ ✅ 原生点击           │ ✅       │ ✅           │ ✅ 适配器    │ ✅ 适配器               │
├────────────┼───────────────────────┼──────────┼──────────────┼──────────────┼─────────────────────────┤
│ scroll     │ ✅ JS scrollBy        │ ✅       │ ✅           │ ✅           │ ✅                      │
├────────────┼───────────────────────┼──────────┼──────────────┼──────────────┼─────────────────────────┤
│ proxy      │ ✅ proxy参数          │ ✅       │ ✅           │ ✅ proxy=    │ ✅ --proxy-server       │
├────────────┼───────────────────────┼──────────┼──────────────┼──────────────┼─────────────────────────┤
│ hover      │ ✅ 贝塞尔曲线移动     │ ✅       │ ✅           │ ✅           │ ✅                      │
├────────────┼───────────────────────┼──────────┼──────────────┼──────────────┼─────────────────────────┤
│ human_click│ ✅ 贝塞尔曲线+点击    │ ✅       │ ✅           │ ✅           │ ✅                      │
├────────────┼───────────────────────┼──────────┼──────────────┼──────────────┼─────────────────────────┤
│ drag       │ ✅ mouse.down/up      │ ✅       │ ✅           │ ✅ JS回退   │ ✅ JS回退               │
├────────────┼───────────────────────┼──────────┼──────────────┼──────────────┼─────────────────────────┤
│ human_scroll│ ✅ 人类滚轮          │ ✅       │ ✅           │ ✅           │ ✅                      │
└────────────┴───────────────────────┴──────────┴──────────────┴──────────────┴─────────────────────────┘
```

## MouseAdapter Assignment

| Backend                    | Adapter                  | Target Object        |
| -------------------------- | ------------------------ | -------------------- |
| playwright                 | PlaywrightMouseAdapter   | page (Playwright)    |
| camoufox                   | PlaywrightMouseAdapter   | page (Playwright)    |
| cloakbrowser               | PlaywrightMouseAdapter   | page (Playwright)    |
| seleniumbase               | SeleniumMouseAdapter     | page._driver (SB)    |
| undetected_chromedriver    | SeleniumMouseAdapter     | page._driver (UC)    |

## Proxy Configuration

| Backend                    | Mechanism                                    |
| -------------------------- | -------------------------------------------- |
| playwright                 | `launch_kwargs["proxy"] = {"server": proxy}` |
| camoufox                   | `launch_kwargs["proxy"] = {"server": proxy}` |
| cloakbrowser               | `CloakBrowserWrapper(proxy=proxy)`           |
| seleniumbase               | `Driver(proxy=proxy)`                        |
| undetected_chromedriver    | `options.add_argument("--proxy-server=...")` |

## SeleniumPageAdapter

Wraps Selenium WebDriver to expose a Playwright-like page API. Used by seleniumbase and undetected_chromedriver backends.

Methods implemented for BrowserOperator compatibility:

- `content()` → `driver.page_source`
- `goto(url, wait_until, timeout)` → `driver.get()` + readyState wait
- `click(selector, timeout)` → `WebDriverWait` + `element.click()`
- `evaluate(js)` → `driver.execute_script()`
- `wait_for_selector(selector, timeout)` → `WebDriverWait` presence
- `wait_for_function(js, timeout)` → `WebDriverWait` lambda
- `screenshot(path)` → `driver.save_screenshot()`
- `keyboard.type(char)` → `ActionChains.send_keys()`
- `keyboard.press(key)` → key map + `ActionChains.send_keys()`
- `route()` / `unroute()` → no-ops (network capture not supported)
- `close()` → `driver.quit()`

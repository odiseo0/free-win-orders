# PARSE_EXECUTOR = ThreadPoolExecutor(max_workers=PARSE_MAX_WORKERS)

# this is supposed to be part of the transforming and loading process.
#    loop = asyncio.get_running_loop()

#   parse_tasks = [
#        loop.run_in_executor(PARSE_EXECUTOR, parse_card_listings, html, card_name)
#        for card_name, html in zip(card_names, htmls)
#        if html
#    ]

#    parsed_lists = await asyncio.gather(*parse_tasks)

#    now_after_parse = time.monotonic()

#    for card_name, listings in zip(card_names, parsed_lists):
#        key = _card_cache_key(card_name)
#        _CARD_LISTINGS_CACHE[key] = (
#            now_after_parse + CARD_LISTINGS_TTL_SECONDS,
#            listings,
#        )
#        all_listings.extend(listings)

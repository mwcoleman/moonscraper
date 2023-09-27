# moonscraper

A no frills moonboard logbook scraper. 

Outputs 1) a JSON of your moonboard account logbook; 2) accompanying screenshots of each problem.

## Acknowledgements
Selenium code based on https://github.com/yesoer/MoonPlotter 

## Usage
`python main.py -u [USERNAME] -p [PASSWORD] -b [BOARD] -o [OUTPUT PATH]`

Where `BOARD` is one of {0: 2020 mini, 1: 2019, 2: 2017, 3: 2016}
and `OUTPUT PATH` is relative output where `data.json` and `/images/` are saved


## TODO

- Integrate with reflex logbook
- Log attempts for each problem
- Dynamic wait for element (currently a simple timer)
- CLI option to specify date
- Check existing data and only scrape newer dates

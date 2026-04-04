currently working on
- get region and solar model
- using predictive model to find the powers produced
    - can include graphs
    - can draw regions
    - etc.

additional ideas
- Allow solar installers, grid operators, or real estate platforms to ping your backend directly from their own CRM (like Salesforce) to instantly score leads or assess property viability. Charge them based on API call volume
- create and update dataset hosted on mongol
    - update with new models and new specs, etc.
- add functionality for Levelized Cost of Energy (LCOE), estimated payback periods, and internal rate of return (IRR)
- dynamic monitoring: as equipment prices fluctuate, local grid tariffs change, or new tax incentives are passed, your software can automatically send them an alert: "Site C is now 15% more profitable to develop than it was last month"
    - tell user when they should invest (based on current trends)


TARGET CORPS
- EPCs (Engineering, Procurement, and Construction) & Installers: They need to quickly assess if a prospective client's site is worth bidding on. Your tool speeds up their sales cycle.
- Commercial Real Estate Developers: Large property owners are increasingly looking to monetize their roof space or land. Your software acts as an asset-evaluation tool for their existing portfolios.
- Corporate ESG Teams: Large corporations have strict carbon-neutral goals. They need software to figure out the most cost-effective regions to deploy their renewable energy budgets.


=====

https://energy.usgs.gov/uswtdb/data/
https://energy.usgs.gov/uspvdb/data/

=====

windpower
solarpower
hydropower

- equipment
- dimension/placement constraint
- how much power output based on resource input
- input graph over a year
- input based on climate/terrain/etc.

formula for power compute
- no. of equipment: equipment/place dimension 
no. of equipment * power/equipment based on input
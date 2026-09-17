# Query export notes

The dashboard consumes the final outputs of these warehouse queries:

- Finance: week field `month`; template `data/templates/finance_template.csv`
- Reserve Rate: week field `Timeperiod`; template `data/templates/reserve_rate_template.csv`
- Return Rate: week field `month`; template `data/templates/return_rate_template.csv`
- Sessions: week field `week`; template `data/templates/sessions_template.csv`
- Experiment: week field `month`, with `cohort`; template
  `data/templates/experiment_template.csv`
- Promo Redemption: week field `month`; template
  `data/templates/promo_redemption_template.csv`

Before running each source query, set `{{start_date}}`, `{{end_date}}`, and
`{{vvid}}`. Export the final result as CSV or XLSX without renaming columns.

Only Brazil and Mexico rows are in scope. The Spain-specific union branches in
the original global queries are not part of this LATAM dashboard.

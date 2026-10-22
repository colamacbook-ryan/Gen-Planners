# Cấu trúc gọi vốn

- Vốn gọi: {{ fin.base.metrics.raise_amount|money }}
- Định giá trước vốn: {{ fin.base.metrics.pre_money|money }} → sau vốn {{ fin.base.metrics.post_money|money }}
- Tỷ lệ nhà đầu tư: {{ fin.base.metrics.investor_stake|pct(1) }}
- Giá trị thoát vốn ước tính năm {{ fin.base.last.year }}: {{ fin.base.metrics.exit_value|money }} → nhà đầu tư nhận {{ fin.base.metrics.investor_exit|money }} ({{ fin.base.metrics.investor_moic|num(1) }}x)

TODO(stage 10): use of funds, cap table, sweat equity & vesting, giải ngân theo milestone.

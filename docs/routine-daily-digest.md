# Routine notification delivery

`QSL_ROUTINE_NOTIFICATION_MODE` defaults to `immediate`. The optional
`daily_digest` mode moves verified, healthy no-order cycle notifications into
the existing daily report. Integrate `defer_routine_cycle_to_digest` only at the
notification boundary, after existing attention/error checks. Persist the
original execution report and keep private daily-candidate production enabled.
Deferral is not a Telegram delivery acknowledgement.

Risk blocks, pending or unknown orders, reconciliation problems, errors, and
real order activity remain immediate. Do not silence alerts because another
alert was attempted, or infer success from a scheduler or CI result.

Use the existing central digest aggregator: one message containing all verified
account/strategy observations for the business window. Locale is configured
independently (`zh-CN` or `en`); account identity and routes come from private
configuration, never repository examples. Keep unknown counts unknown and show
missing/stale coverage.

Before enabling the mode for one producer, its owner must verify fresh private
candidates, matching target/business day, central receipt, actual delivery, and
the immediate exception path. Flag changes and deployment require owner
approval. No new service, bot, database, scheduler or permissions are required.

中文：默认保持原通知方式。完成现有日报的候选、日期、覆盖和真实送达验证后，
负责人可批准一个平台切换。正常无单周期进入同一份日报；风控拒绝、订单未知、
待对账、运行异常和真实订单继续即时通知。日报使用配置的中文或英文模板。

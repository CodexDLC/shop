# Оплата: способы и провайдер

Актуальный [сравнительный анализ тарифов и Python-интеграции от 15.10.2026](payment-provider-comparison.md). Приоритет проверки: Stripe Checkout с PayPal, Mollie остаётся кандидатом; окончательный выбор не сделан. Раннее предпочтение Mollie ниже является исторической предварительной оценкой.

Обновлено 13.10.2026. Требование пользователя: привычные немецким покупателям способы, обязательно PayPal. «Самый популярный способ» и «провайдер API» — разные решения.

EHI в исследовании 2026 по данным 2025 указывает доли онлайн-оборота: PayPal 28,7%, Rechnung 26,1%, Lastschrift 14,4%, карты 13,7%. Это доли оборота панели исследования, не доли покупателей нашего магазина. [EHI 2026](https://www.ehi.org/presse/smartphone-statt-portemonnaie-mobile-payment-boomt/).

Первоначальный набор: PayPal + карты; покупка по счёту через подходящего провайдера — кандидат на следующий метод. SEPA/wallets добавляем по потребности. Собственное кредитование покупки по счёту не подразумевается.

Кандидаты единого PSP: Mollie и Stripe. Mollie документирует PayPal, карты и Klarna; Stripe поддерживает PayPal для бизнеса в Германии как части разрешённых стран EU. [Mollie methods](https://docs.mollie.com/docs/payment-methods), [Stripe PayPal availability](https://support.stripe.com/questions/paypal-payment-method-availability?locale=en-GB).

Предварительный кандидат для проверки — Mollie с hosted checkout, Stripe остаётся альтернативой. Окончательно не выбран: проверяем доступ методов для аккаунта/ассортимента, подключение PayPal business, стоимость, refunds, disputes, сроки выплат и sandbox. Наличие метода в документации не гарантирует включение для аккаунта. [Mollie activation](https://help.mollie.com/hc/en-us/articles/115000648269-How-do-I-activate-a-payment-method).

Движок содержит независимый PaymentGateway contract; provider SDK — в адаптере, Django только подключает его. В домен не попадают provider-specific статусы без нормализации. Прямой PayPal adapter возможен, но не обязателен, если выбранный PSP закрывает нужные методы.

(() => {
  const form = document.getElementById('checkout-address-form');
  if (!form) return;
  const billing = form.querySelector('[name="billing_separate"]');
  const toggle = (block, active) => {
    block.hidden = !active;
    block.querySelectorAll('input,select').forEach(input => { input.disabled = !active; });
  };
  const update = () => {
    const station = form.querySelector('[name="shipping_type"]:checked')?.value === 'packstation';
    if (station) billing.checked = true;
    toggle(form.querySelector('[data-packstation-fields]'), station);
    toggle(form.querySelector('[data-billing-fields]'), billing.checked);
    const street = form.querySelector('[name="street"]');
    street.disabled = station;
    street.parentElement.hidden = station;
  };
  form.addEventListener('change', event => {
    if (['shipping_type', 'billing_separate'].includes(event.target.name)) update();
  });
  update();
})();

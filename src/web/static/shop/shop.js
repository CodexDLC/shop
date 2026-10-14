"use strict";
const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#main-nav");
menuButton.addEventListener("click", () => {
  const expanded = menuButton.getAttribute("aria-expanded") !== "true";
  menuButton.setAttribute("aria-expanded", String(expanded));
  navigation.classList.toggle("is-open", expanded);
});
navigation.addEventListener("click", (event) => {
  if (event.target.closest("a")) {
    menuButton.setAttribute("aria-expanded", "false");
    navigation.classList.remove("is-open");
  }
});
function filterProducts(category) {
  let count = 0;
  document.querySelectorAll(".product").forEach((card) => {
    card.hidden = category !== "all" && card.dataset.category !== category;
    if (!card.hidden) count += 1;
  });
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.filter === category));
  });
  document.querySelector("#filter-status").textContent = `${count} Beispielartikel angezeigt.`;
}
document.querySelectorAll("[data-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    filterProducts(button.dataset.filter);
    document.querySelector("#products").scrollIntoView({behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
  });
});
document.querySelector("#reset-filter").addEventListener("click", () => filterProducts("all"));
document.querySelector("[data-nav-filter]").addEventListener("click", () => filterProducts("all"));
const products = JSON.parse(document.querySelector("#demo-products").textContent);
const dialog = document.querySelector("#product-dialog");
const color = document.querySelector("#demo-color");
const size = document.querySelector("#demo-size");
const illustration = document.querySelector("#dialog-image");
function updateVariant() {
  document.querySelector("#variant-status").textContent = `Auswahl: ${color.value} / ${size.value} · Demonstrationsvariante`;
  illustration.style.filter = {Schwarz:"none", Waldgrün:"sepia(.5) hue-rotate(45deg)", Sand:"sepia(.8) brightness(1.8)"}[color.value];
  illustration.alt = `Illustration in ${color.value}; kein Herstellerfoto`;
}
document.querySelectorAll("[data-product]").forEach((button) => {
  button.addEventListener("click", () => {
    const product = products.find((item) => item.id === button.dataset.product);
    document.querySelector("#dialog-brand").textContent = product.brand;
    document.querySelector("#dialog-title").textContent = product.name;
    document.querySelector("#dialog-price").textContent = `${product.price} € · Beispielpreis`;
    illustration.src = button.querySelector("img").src;
    color.value = "Schwarz";
    size.value = "M";
    updateVariant();
    dialog.showModal();
  });
});
color.addEventListener("change", updateVariant);
size.addEventListener("change", updateVariant);
document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());

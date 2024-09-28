function wheelOfFortune(selector) {
    const node = document.querySelector(selector);
    if (!node) return;
  
    const spin = node.querySelector('button');
    const wheel = node.querySelector('ul');
    let animation;
    let previousEndDegree = 0;
  
    spin.addEventListener('click', () => {
      if (animation) {
        animation.cancel(); // Reset the animation if it already exists
      }
  
      const randomAdditionalDegrees = Math.random() * 360 + 1800;
      const newEndDegree = previousEndDegree + randomAdditionalDegrees;
  
      animation = wheel.animate([
        { transform: `rotate(${previousEndDegree}deg)` },
        { transform: `rotate(${newEndDegree}deg)` }
      ], {
        duration: 4000,
        direction: 'normal',
        easing: 'cubic-bezier(0.440, -0.205, 0.000, 1.130)',
        fill: 'forwards',
        iterations: 1
      });
  
      previousEndDegree = newEndDegree;
  
      // Интеграция с Telegram WebApp: отправка данных при завершении анимации
      animation.onfinish = () => {
        const selectedItemIndex = Math.floor(newEndDegree / (360 / 12)) % 12;
        const selectedItem = wheel.children[selectedItemIndex].textContent.trim();
        
        // Отправка данных в бот
        Telegram.WebApp.sendData(selectedItem); // отправляет выбранную скидку обратно в бот
      };
    });
  }
  
  // Запуск колеса фортуны
  wheelOfFortune('.ui-wheel-of-fortune');
  
  // Инициализация Telegram WebApp
  Telegram.WebApp.ready();
  
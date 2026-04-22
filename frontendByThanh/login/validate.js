function Validate(rule, inputElement, errorElement, selectorRules) {
    var errorMessage;
    var rules = selectorRules[rule.selector];

    for (var i = 0; i < rules.length; i++) {
        errorMessage = rules[i](inputElement.value);
        if (errorMessage) break;
    }
    if (errorMessage) {
        errorElement.innerText = errorMessage;
        inputElement.parentElement.classList.add('invalid');
    } else {
        errorElement.innerText = '';
        inputElement.parentElement.classList.remove('invalid');
    }
    return !errorMessage;
}

function Validator(options) {
    var getForm = document.querySelector(options.form);
    var selectorRules = {};
    if (getForm) {
        options.rules.forEach(rule => {
            var inputElement = getForm.querySelector(rule.selector);
            var errorElement = inputElement ? inputElement.parentElement.querySelector(options.errorSelector) : null;

            if (Array.isArray(selectorRules[rule.selector])) {
                selectorRules[rule.selector].push(rule.test);
            } else {
                selectorRules[rule.selector] = [rule.test];
            }

            if (inputElement) {
                inputElement.onblur = () => {
                    Validate(rule, inputElement, errorElement, selectorRules);

                }
                inputElement.oninput = () => {
                    errorElement.innerText = '';
                    inputElement.parentElement.classList.remove('invalid');
                }
            }
        })

        getForm.onsubmit = e => {
            e.preventDefault();
            var isFormValid = true;
            options.rules.forEach(rule => {
                var inputElement = getForm.querySelector(rule.selector);
                if (!inputElement) return;
                var errorElement = inputElement.parentElement.querySelector(options.errorSelector);
                var check = Validate(rule, inputElement, errorElement, selectorRules);
                if (!check) {
                    isFormValid = false;
                }
            })

            if (isFormValid) {
                if (typeof options.submit === 'function') {
                    var enableInputs = getForm.querySelectorAll('[name]');
                    var formValue = Array.from(enableInputs).reduce((values, input) => {
                        values[input.name] = input.value;
                        return values;
                    }, {});
                    delete formValue['password_confirmation'];
                    options.submit(formValue);
                }
            }
        }
    }
}

Validator.isRequired = (selector, message) => {
    return {
        selector,
        test: value => value.trim() ? undefined : message || 'Error'
    }
}

Validator.isEmail = (selector, message) => {
    return {
        selector,
        test: value => {
            const regex = /^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$/;
            return regex.test(value) ? undefined : message || 'Error'
        }
    }
}

Validator.minLength = (selector, min, message) => {
    return {
        selector,
        test: value => value.length >= min ? undefined : message || `Vui lòng nhập tối thiểu ${min} ký tự`
    }
}

Validator.isConfirmed = (selector, getConfirmValue, message) => {
    return {
        selector,
        test: value => value === getConfirmValue() && value.length >= 6 ? undefined : message || 'Giá trị nhập vào không chính xác'
    }
}

Validator({
    form: '#form-1',
    errorSelector: '.form-message',
    rules: [
        Validator.isRequired('#fullname', 'Vui lòng nhập tên đầy đủ của bạn'),
        Validator.isRequired('#email', 'Vui lòng nhập email của bạn'),
        Validator.isEmail('#email', 'Vui lòng nhập đúng định dạng email'),
        Validator.isRequired('#password', 'Vui lòng nhập mật khẩu của bạn'),
        Validator.minLength('#password', 6),
        Validator.isRequired('#password_confirmation', 'Vui lòng nhập lại mật khẩu của bạn'),
        Validator.isConfirmed('#password_confirmation', () => {
            return document.querySelector('#form-1 #password').value;
        })
    ],
    submit: (data) => {
        fetch(accAPI, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
            .then(response => response.json())
            .then(data => {
                console.log(data);
                alert('Đăng ký thành công!');
            })
            .catch(() => {
                alert('Đăng ký thất bại!');
            });
    }
})



Validator({
    form: '#form-2',
    errorSelector: '.form-message',
    rules: [
        Validator.isRequired('#email', 'Vui lòng nhập email của bạn'),
        Validator.isEmail('#email', 'Vui lòng nhập đúng định dạng email'),
        Validator.isRequired('#password', 'Vui lòng nhập mật khẩu của bạn'),
        Validator.minLength('#password', 6),
        Validator.isRequired('#key_esp', 'Vui lòng nhập mã ESP của bạn')
    ],
    submit: async (data) => {
        console.log(data);

        fetch(API_URL + '/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
            credentials: 'include'
        })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Đăng nhập thất bại');
                }
            })
            .then(data => {
                alert(data.message);
                window.location.href = '../index.html';
            })
            .catch(err => {
                alert('Email hoặc mật khẩu hoặc Key không chính xác.');
            });
    }
})
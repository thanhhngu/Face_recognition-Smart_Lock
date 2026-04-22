CREATE DATABASE IF NOT EXISTS smart_lock;
USE smart_lock;

CREATE TABLE key_devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    api_key VARCHAR(100) UNIQUE NOT NULL,
    device_name VARCHAR(100) NOT NULL
);

CREATE TABLE account (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    api_key VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (api_key) REFERENCES key_devices(api_key) ON DELETE CASCADE
);

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    api_key VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL,
    FOREIGN KEY (api_key) REFERENCES account(api_key) ON DELETE CASCADE
);

CREATE TABLE face_encodings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    encoding JSON NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE access_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

INSERT INTO `smart_lock`.`key_devices` (`id`, `api_key`, `device_name`) VALUES ('1', '1234567890', 'esp1');

INSERT INTO `smart_lock`.`account` (`id`, `email`, `password_hash`, `api_key`) VALUES ('1', 'thanhhngu06@gmail.com', '123456', '1234567890');

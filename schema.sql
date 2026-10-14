CREATE DATABASE IF NOT EXISTS tictactoe CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE tictactoe;

CREATE TABLE IF NOT EXISTS guests (
  id CHAR(32) PRIMARY KEY,
  name VARCHAR(16) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS matches (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  player_x CHAR(32) NOT NULL,
  player_o CHAR(32) NOT NULL,
  winner_id CHAR(32) NULL,               -- NULL = draw
  result ENUM('win','draw','forfeit') NOT NULL,
  moves VARCHAR(32) NOT NULL,            -- cell indexes in play order, e.g. "4,0,8"
  played_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (player_x) REFERENCES guests(id) ON DELETE CASCADE,
  FOREIGN KEY (player_o) REFERENCES guests(id) ON DELETE CASCADE,
  INDEX idx_x (player_x), INDEX idx_o (player_o), INDEX idx_played (played_at)
) ENGINE=InnoDB;

-- Least-privilege app user (change the password!):
-- CREATE USER 'ttt_app'@'%' IDENTIFIED BY 'change-me';
-- GRANT SELECT, INSERT, UPDATE ON tictactoe.* TO 'ttt_app'@'%';

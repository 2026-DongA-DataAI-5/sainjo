-- 선택한 질문 키만 저장합니다. 차량과 함께 삭제되며 정비기록에는 영향을 주지 않습니다.
CREATE TABLE IF NOT EXISTS question_selections (
    vehicle_id INT UNSIGNED NOT NULL,
    question_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (vehicle_id, question_key),
    CONSTRAINT fk_question_selections_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicles (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

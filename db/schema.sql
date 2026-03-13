CREATE TABLE "persons" (
    "id" INTEGER,
    "first_name" TEXT NOT NULL,
    "last_name" TEXT NOT NULL,
    "email" TEXT,
    hash TEXT NOT NULL,
-- Format validation from 8 (Norwegian local) to 15 international
    "phone" TEXT CHECK(length("phone") BETWEEN 8 AND 15),
    PRIMARY KEY ("id")
);

-- AUTOPASS Device (Human-Machine Communication)
CREATE TABLE "auto_pass" (
    "id" INTEGER,
    "person_id" INTEGER,
    "car_num" TEXT,
    PRIMARY KEY("id"),
    FOREIGN KEY("person_id") REFERENCES "persons"("id"),
    FOREIGN KEY("car_num") REFERENCES "vehicles"("car_num")
);


CREATE TABLE "vehicles" (
    "car_num" TEXT NOT NULL UNIQUE,
    "fuel_type" INTEGER NOT NULL DEFAULT 0 CHECK("fuel_type" IN (0, 1, 2, 3)),
    "discount_percent" INTEGER GENERATED ALWAYS AS (
        CASE
            WHEN "fuel_type" = 1 THEN 20 -- Diesel/Gasoline
            WHEN "fuel_type" = 2 THEN 30 -- Hybrid
            WHEN "fuel_type" = 3 THEN 50 -- Electro
            ELSE 0
        END
    ) STORED,
    PRIMARY KEY("car_num")
);

-- Stations that record the fact of travel
CREATE TABLE "toll_stations" (
    "id" INTEGER,
    "name" TEXT NOT NULL,
    "base_price" INTEGER NOT NULL, -- Price in øre (kopecks)
    PRIMARY KEY("id")
);

--Transactional Log records every fact of trave
CREATE TABLE "passages" (
    "id" INTEGER,
    "car_num" TEXT,
    "station_id" INTEGER,
    "passed_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY("id"),
    FOREIGN KEY("car_num") REFERENCES "vehicles"("car_num"),
    FOREIGN KEY("station_id") REFERENCES "toll_stations"("id")
);

---###############################################

CREATE VIEW "all_passages" AS
SELECT
    "passages"."id" AS "passage_id",
    "passages"."passed_at",
    "vehicles"."car_num",
    "toll_stations"."name" AS "station",
    "toll_stations"."base_price",
    "vehicles"."discount_percent",

--Rush Hour Logic
--Morning (07:00-08:30) and Evening (15:30-17:00) -> Markup +20% (x1.2)
    CASE
        WHEN (CAST(strftime('%H', "passages"."passed_at") AS INTEGER) = 7) -- 07:00-07:59
          OR (CAST(strftime('%H', "passages"."passed_at") AS INTEGER) = 8 AND CAST(strftime('%M', "passages"."passed_at") AS INTEGER) <= 30) -- 08:00-08:30
          OR (CAST(strftime('%H', "passages"."passed_at") AS INTEGER) = 15 AND CAST(strftime('%M', "passages"."passed_at") AS INTEGER) >= 30) -- Норвезький пік часто з 15:30
          OR (CAST(strftime('%H', "passages"."passed_at") AS INTEGER) = 16)
        THEN 1.2 --+20% surcharge during rush hour
        ELSE 1.0
    END AS "time_multiplier",

    -- Фінальна формула
    CAST(
    ROUND(
        ("toll_stations"."base_price" * (100 - "vehicles"."discount_percent") / 100) * -- Базова зі знижкою
        CASE
            WHEN (CAST(strftime('%H', "passages"."passed_at") AS INTEGER) = 7) -- 07:00-07:59
            OR (CAST(strftime('%H', "passages"."passed_at") AS INTEGER) = 8 AND CAST(strftime('%M', "passages"."passed_at") AS INTEGER) <= 30) -- 08:00-08:30
            OR (CAST(strftime('%H', "passages"."passed_at") AS INTEGER) = 15 AND CAST(strftime('%M', "passages"."passed_at") AS INTEGER) >= 30) -- Норвезький пік часто з 15:30
            OR (CAST(strftime('%H', "passages"."passed_at") AS INTEGER) = 16)
            THEN 1.2
            ELSE 1.0
        END
    )
    AS INTEGER) AS "final_price_ore"

FROM "passages"
JOIN "vehicles" ON "passages"."car_num" = "vehicles"."car_num"
JOIN "toll_stations" ON "passages"."station_id" = "toll_stations"."id";


---##########################################
CREATE TRIGGER "register_unknown_car"
BEFORE INSERT ON "passages"
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM "vehicles" WHERE "car_num" = NEW."car_num")
BEGIN
    INSERT INTO "vehicles" ("car_num")
    VALUES (NEW."car_num");
END;

---#########################################
CREATE INDEX "idx_passages_passed_at" ON "passages"("passed_at");
CREATE INDEX "idx_passages_station" ON "passages" ("station_id");
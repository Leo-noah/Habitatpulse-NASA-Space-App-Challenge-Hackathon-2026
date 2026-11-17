-- MySQL dump 10.13  Distrib 9.3.0, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: habitatpulse
-- ------------------------------------------------------
-- Server version	9.3.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `checkins`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `checkins` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `crew_id` bigint NOT NULL,
  `recorded_at_utc` datetime(6) NOT NULL,
  `module_id` bigint NOT NULL,
  `current_mission_task` text COLLATE utf8mb4_unicode_ci,
  `recent_task_completed` text COLLATE utf8mb4_unicode_ci,
  `notes` text COLLATE utf8mb4_unicode_ci,
  `overall_wellbeing` tinyint NOT NULL,
  `fatigue_level` enum('none','mild','moderate','severe') COLLATE utf8mb4_unicode_ci NOT NULL,
  `mood_stress_level` tinyint NOT NULL,
  `sleep_hours` decimal(5,2) NOT NULL,
  `sleep_quality` enum('poor','fair','good') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fluid_intake_ml` int NOT NULL,
  `appetite` enum('reduced','normal','increased') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `activity_level` enum('low','normal','high') COLLATE utf8mb4_unicode_ci NOT NULL,
  `exercise_completed` tinyint(1) DEFAULT NULL,
  `medication_taken` enum('yes','no','not_applicable') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at_utc` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `fk_checkin_module` (`module_id`),
  KEY `idx_checkin_crew_time` (`crew_id`,`recorded_at_utc`),
  CONSTRAINT `fk_checkin_crew` FOREIGN KEY (`crew_id`) REFERENCES `crew_members` (`id`),
  CONSTRAINT `fk_checkin_module` FOREIGN KEY (`module_id`) REFERENCES `habitat_modules` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=558 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `crew_members`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `crew_members` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `crew_code` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(160) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mission_id` bigint DEFAULT NULL,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at_utc` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `crew_code` (`crew_code`),
  KEY `fk_crew_mission` (`mission_id`),
  CONSTRAINT `fk_crew_mission` FOREIGN KEY (`mission_id`) REFERENCES `missions` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `environment_records`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `environment_records` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `measured_at_utc` datetime(6) NOT NULL,
  `module_id` bigint NOT NULL,
  `source_id` bigint NOT NULL,
  `is_simulated` tinyint(1) NOT NULL,
  `temperature_c` decimal(6,2) NOT NULL,
  `humidity_percent` decimal(6,2) NOT NULL,
  `co2_ppm` decimal(10,2) NOT NULL,
  `anomaly_score` decimal(12,8) NOT NULL,
  `anomaly_threshold` decimal(12,8) NOT NULL,
  `anomaly_flag` tinyint(1) NOT NULL,
  `anomaly_model_version` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `saved_at_utc` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_environment_time` (`measured_at_utc`),
  KEY `idx_environment_module_time` (`module_id`,`measured_at_utc`),
  KEY `fk_environment_source` (`source_id`),
  CONSTRAINT `fk_environment_module` FOREIGN KEY (`module_id`) REFERENCES `habitat_modules` (`id`),
  CONSTRAINT `fk_environment_source` FOREIGN KEY (`source_id`) REFERENCES `sensor_sources` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=161720 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `habitat_modules`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `habitat_modules` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `module_code` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `module_name` varchar(160) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mission_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `module_code` (`module_code`),
  KEY `fk_module_mission` (`mission_id`),
  CONSTRAINT `fk_module_mission` FOREIGN KEY (`mission_id`) REFERENCES `missions` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `health_reports`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `health_reports` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `report_code` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `checkin_id` bigint NOT NULL,
  `workflow_status` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ruleset_version` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at_utc` datetime(6) NOT NULL,
  `medical_review_required` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `report_code` (`report_code`),
  KEY `idx_report_checkin` (`checkin_id`),
  CONSTRAINT `fk_report_checkin` FOREIGN KEY (`checkin_id`) REFERENCES `checkins` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=68 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `medication_inventory`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `medication_inventory` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `medication_name` varchar(160) COLLATE utf8mb4_unicode_ci NOT NULL,
  `form_description` varchar(160) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quantity_available` int NOT NULL DEFAULT '0',
  `expiry_date` date DEFAULT NULL,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `medication_review_requests`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `medication_review_requests` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `checkin_id` bigint NOT NULL,
  `inventory_id` bigint DEFAULT NULL,
  `request_reason` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('pending_medical_review','approved','rejected') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending_medical_review',
  `requested_at_utc` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `reviewer_note` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `fk_medication_request_checkin` (`checkin_id`),
  KEY `fk_medication_request_inventory` (`inventory_id`),
  CONSTRAINT `fk_medication_request_checkin` FOREIGN KEY (`checkin_id`) REFERENCES `checkins` (`id`),
  CONSTRAINT `fk_medication_request_inventory` FOREIGN KEY (`inventory_id`) REFERENCES `medication_inventory` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `missions`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `missions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `mission_code` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `mission_name` varchar(160) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at_utc` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `mission_code` (`mission_code`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `outbox`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `outbox` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `entity_type` enum('environment_record','checkin','health_report','task_delay_request','medication_review_request') COLLATE utf8mb4_unicode_ci NOT NULL,
  `entity_id` bigint NOT NULL,
  `status` enum('pending_sync','sent','confirmed','failed') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending_sync',
  `created_at_utc` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `sent_at_utc` datetime(6) DEFAULT NULL,
  `confirmed_at_utc` datetime(6) DEFAULT NULL,
  `last_error` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `idx_outbox_status` (`status`,`created_at_utc`)
) ENGINE=InnoDB AUTO_INCREMENT=627 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `report_evidence`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_evidence` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `report_id` bigint NOT NULL,
  `evidence_type` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(160) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_reference` varchar(160) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `note` text COLLATE utf8mb4_unicode_ci,
  `environment_record_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_evidence_report` (`report_id`),
  KEY `fk_evidence_environment` (`environment_record_id`),
  CONSTRAINT `fk_evidence_environment` FOREIGN KEY (`environment_record_id`) REFERENCES `environment_records` (`id`),
  CONSTRAINT `fk_evidence_report` FOREIGN KEY (`report_id`) REFERENCES `health_reports` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=69 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `safety_reviews`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `safety_reviews` (
  `checkin_id` bigint NOT NULL,
  `severe_chest_discomfort` tinyint(1) DEFAULT NULL,
  `severe_breathing_difficulty` tinyint(1) DEFAULT NULL,
  `loss_of_consciousness` tinyint(1) DEFAULT NULL,
  `sudden_neurological_change` tinyint(1) DEFAULT NULL,
  `sudden_severe_headache` tinyint(1) DEFAULT NULL,
  `rapidly_worsening_symptoms` tinyint(1) DEFAULT NULL,
  `urgent_human_review_required` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`checkin_id`),
  CONSTRAINT `fk_safety_checkin` FOREIGN KEY (`checkin_id`) REFERENCES `checkins` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sensor_sources`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sensor_sources` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `source_code` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_name` varchar(160) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_simulated` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `source_code` (`source_code`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `symptom_detail_answers`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `symptom_detail_answers` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `symptom_id` bigint NOT NULL,
  `field_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `value_text` text COLLATE utf8mb4_unicode_ci,
  `value_number` decimal(12,4) DEFAULT NULL,
  `value_boolean` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_symptom_detail` (`symptom_id`,`field_name`),
  CONSTRAINT `fk_detail_symptom` FOREIGN KEY (`symptom_id`) REFERENCES `symptom_records` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=95 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `symptom_records`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `symptom_records` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `checkin_id` bigint NOT NULL,
  `symptom_name` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `severity_0_to_10` tinyint DEFAULT NULL,
  `onset_at_utc` datetime(6) DEFAULT NULL,
  `onset_status` enum('known','unknown') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'known',
  `duration_minutes` int DEFAULT NULL,
  `duration_status` enum('known','ongoing','unknown') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'known',
  `symptom_pattern` enum('constant','intermittent') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `progression` enum('improving','stable','worsening') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mission_task_effect` enum('none','some_difficulty','unable_to_perform_safely') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `similar_episode` enum('yes','no','unknown') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `action_or_medication_taken` text COLLATE utf8mb4_unicode_ci,
  `note` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `idx_symptom_checkin` (`checkin_id`),
  CONSTRAINT `fk_symptom_checkin` FOREIGN KEY (`checkin_id`) REFERENCES `checkins` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=70 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `task_delay_requests`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `task_delay_requests` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `checkin_id` bigint NOT NULL,
  `task_name` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `medical_reason_summary` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('draft','pending_approval','approved','rejected') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'draft',
  `requested_at_utc` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `reviewer_note` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `fk_task_delay_checkin` (`checkin_id`),
  CONSTRAINT `fk_task_delay_checkin` FOREIGN KEY (`checkin_id`) REFERENCES `checkins` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vital_signs`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `vital_signs` (
  `checkin_id` bigint NOT NULL,
  `heart_rate_bpm` decimal(8,2) DEFAULT NULL,
  `spo2_percent` decimal(6,2) DEFAULT NULL,
  `respiratory_rate_bpm` decimal(8,2) DEFAULT NULL,
  `body_temperature_c` decimal(5,2) DEFAULT NULL,
  `blood_pressure_systolic` decimal(8,2) DEFAULT NULL,
  `blood_pressure_diastolic` decimal(8,2) DEFAULT NULL,
  `hrv_ms` decimal(10,2) DEFAULT NULL,
  `weight_kg` decimal(8,2) DEFAULT NULL,
  PRIMARY KEY (`checkin_id`),
  CONSTRAINT `fk_vitals_checkin` FOREIGN KEY (`checkin_id`) REFERENCES `checkins` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-11-17 12:21:23

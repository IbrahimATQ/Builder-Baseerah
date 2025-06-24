import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  UserIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  SparklesIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from "@heroicons/react/24/outline";

interface PatientCase {
  id: string;
  name: string;
  age: number;
  gender: string;
  criticalFlags: number;
  aiConfidence: number;
  status: "critical" | "warning" | "normal" | "processing";
  lastUpdate: string;
  keyFindings: string[];
  nextAction: string;
  riskScore: "High" | "Moderate" | "Low";
  trends: {
    improving: boolean;
    metric: string;
  };
}

interface MultiPatientOverviewProps {
  className?: string;
}

const MultiPatientOverview: React.FC<MultiPatientOverviewProps> = ({
  className = "",
}) => {
  const [expandedCase, setExpandedCase] = useState<string | null>("case-1");

  const patientCases: PatientCase[] = [
    {
      id: "case-1",
      name: "Ahmed Al-Mansouri",
      age: 45,
      gender: "Male",
      criticalFlags: 2,
      aiConfidence: 94,
      status: "critical",
      lastUpdate: "2 min ago",
      keyFindings: [
        "Pre-diabetes (HbA1c 6.2%)",
        "Severe dyslipidemia (LDL 160 mg/dL)",
        "Reduced renal function (eGFR ~32)",
      ],
      nextAction: "Nephrology referral auto-booked",
      riskScore: "High",
      trends: { improving: false, metric: "Creatinine ↗" },
    },
    {
      id: "case-2",
      name: "Fatima Al-Zahra",
      age: 34,
      gender: "Female",
      criticalFlags: 0,
      aiConfidence: 97,
      status: "warning",
      lastUpdate: "15 min ago",
      keyFindings: [
        "Mild anemia (Hgb 10.8 g/dL)",
        "Low vitamin D (18 ng/mL)",
        "Borderline thyroid (TSH 4.2)",
      ],
      nextAction: "Endocrinology consultation recommended",
      riskScore: "Moderate",
      trends: { improving: true, metric: "Iron levels ↗" },
    },
    {
      id: "case-3",
      name: "Omar Al-Rashid",
      age: 28,
      gender: "Male",
      criticalFlags: 0,
      aiConfidence: 99,
      status: "normal",
      lastUpdate: "1 hour ago",
      keyFindings: [
        "All parameters within normal limits",
        "Excellent lipid profile",
        "Optimal kidney function",
      ],
      nextAction: "Annual follow-up scheduled",
      riskScore: "Low",
      trends: { improving: true, metric: "Overall health ↗" },
    },
    {
      id: "case-4",
      name: "Layla Al-Qasimi",
      age: 52,
      gender: "Female",
      criticalFlags: 1,
      aiConfidence: 91,
      status: "processing",
      lastUpdate: "Processing...",
      keyFindings: [
        "Elevated inflammatory markers",
        "Complex lipid panel pending",
        "Additional tests in progress",
      ],
      nextAction: "AI analysis 73% complete",
      riskScore: "Moderate",
      trends: { improving: false, metric: "CRP pending" },
    },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case "critical":
        return "medical-red";
      case "warning":
        return "medical-amber";
      case "normal":
        return "medical-green";
      case "processing":
        return "medical-blue";
      default:
        return "medical-blue";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "critical":
        return <ExclamationTriangleIcon className="w-4 h-4" />;
      case "warning":
        return <ClockIcon className="w-4 h-4" />;
      case "normal":
        return <CheckCircleIcon className="w-4 h-4" />;
      case "processing":
        return <SparklesIcon className="w-4 h-4 animate-spin" />;
      default:
        return <SparklesIcon className="w-4 h-4" />;
    }
  };

  const toggleExpanded = (caseId: string) => {
    setExpandedCase(expandedCase === caseId ? null : caseId);
  };

  return (
    <motion.div
      className={`glass-enhanced rounded-2xl ${className}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
    >
      {/* Header */}
      <div className="p-6 border-b border-medical-glass-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-medical-blue/20">
              <SparklesIcon className="w-6 h-6 text-medical-blue" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-1">
                AI Patient Intelligence Hub
              </h3>
              <p className="text-sm text-muted-foreground">
                Multi-patient analysis with real-time insights
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-medical-blue">
                {patientCases.length}
              </div>
              <div className="text-xs text-muted-foreground">Active Cases</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-medical-red">
                {patientCases.filter((p) => p.criticalFlags > 0).length}
              </div>
              <div className="text-xs text-muted-foreground">Critical</div>
            </div>
          </div>
        </div>
      </div>

      {/* Patient Cases */}
      <div className="p-6 space-y-4">
        {patientCases.map((patient, index) => (
          <motion.div
            key={patient.id}
            className="glass-card rounded-xl border border-medical-glass-border overflow-hidden"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: index * 0.1 }}
          >
            {/* Patient Header */}
            <div
              className="p-4 cursor-pointer hover:bg-medical-glass/30 transition-colors"
              onClick={() => toggleExpanded(patient.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-r from-medical-blue to-medical-teal flex items-center justify-center">
                      <UserIcon className="w-5 h-5 text-white" />
                    </div>
                    {patient.criticalFlags > 0 && (
                      <div className="absolute -top-1 -right-1 w-4 h-4 bg-medical-red rounded-full flex items-center justify-center">
                        <span className="text-xs text-white font-bold">
                          {patient.criticalFlags}
                        </span>
                      </div>
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold text-foreground">
                        {patient.name}
                      </h4>
                      <span className="text-sm text-muted-foreground">
                        {patient.age}Y, {patient.gender}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <div
                        className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-${getStatusColor(
                          patient.status,
                        )}/20 text-${getStatusColor(patient.status)}`}
                      >
                        {getStatusIcon(patient.status)}
                        <span className="capitalize">{patient.status}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {patient.lastUpdate}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <div
                      className={`text-sm font-bold px-2 py-1 rounded text-${getStatusColor(
                        patient.riskScore === "High"
                          ? "critical"
                          : patient.riskScore === "Moderate"
                            ? "warning"
                            : "normal",
                      )}`}
                    >
                      {patient.riskScore} Risk
                    </div>
                    <div className="text-xs text-muted-foreground">
                      AI: {patient.aiConfidence}%
                    </div>
                  </div>
                  <motion.div
                    animate={{ rotate: expandedCase === patient.id ? 90 : 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <ChevronRightIcon className="w-5 h-5 text-muted-foreground" />
                  </motion.div>
                </div>
              </div>
            </div>

            {/* Expanded Details */}
            <AnimatePresence>
              {expandedCase === patient.id && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="border-t border-medical-glass-border"
                >
                  <div className="p-4 bg-medical-dark/20">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Key Findings */}
                      <div>
                        <h5 className="font-semibold text-foreground mb-2">
                          Key Findings
                        </h5>
                        <ul className="space-y-1">
                          {patient.keyFindings.map((finding, i) => (
                            <li
                              key={i}
                              className="text-sm text-muted-foreground flex items-start gap-2"
                            >
                              <span className="w-1 h-1 rounded-full bg-medical-blue mt-2 flex-shrink-0" />
                              {finding}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Actions & Trends */}
                      <div>
                        <h5 className="font-semibold text-foreground mb-2">
                          Next Action
                        </h5>
                        <p className="text-sm text-medical-blue mb-3">
                          {patient.nextAction}
                        </p>

                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            Trend:
                          </span>
                          <span
                            className={`text-xs font-medium ${
                              patient.trends.improving
                                ? "text-medical-green"
                                : "text-medical-amber"
                            }`}
                          >
                            {patient.trends.metric}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Quick Actions */}
                    <div className="mt-4 flex gap-2">
                      <button className="px-3 py-1 bg-medical-blue hover:bg-medical-blue/80 text-white rounded text-xs transition-colors">
                        View Full Report
                      </button>
                      <button className="px-3 py-1 bg-medical-dark/50 hover:bg-medical-dark/70 text-foreground border border-medical-glass-border rounded text-xs transition-colors">
                        Send to Patient
                      </button>
                      {patient.criticalFlags > 0 && (
                        <button className="px-3 py-1 bg-medical-red hover:bg-medical-red/80 text-white rounded text-xs transition-colors">
                          Urgent Action
                        </button>
                      )}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </div>

      {/* Footer Summary */}
      <div className="p-4 border-t border-medical-glass-border bg-medical-dark/20">
        <div className="flex justify-between items-center text-xs text-muted-foreground">
          <span>
            Last AI analysis: {new Date().toLocaleTimeString()} • All systems
            operational
          </span>
          <span>Average processing time: 0.8 seconds</span>
        </div>
      </div>
    </motion.div>
  );
};

export default MultiPatientOverview;

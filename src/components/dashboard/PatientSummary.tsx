import React from "react";
import { motion } from "framer-motion";
import {
  DocumentArrowDownIcon,
  LanguageIcon,
} from "@heroicons/react/24/outline";

interface PatientSummaryProps {
  className?: string;
}

const PatientSummary: React.FC<PatientSummaryProps> = ({ className = "" }) => {
  return (
    <motion.div
      className={`glass-enhanced rounded-xl p-6 ${className}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.2 }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-lg bg-medical-blue/20">
          <LanguageIcon className="w-5 h-5 text-medical-blue" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Patient-Friendly Summary (Arabic & English)
          </h3>
          <p className="text-sm text-muted-foreground">
            Bilingual interpretation for better patient understanding
          </p>
        </div>
      </div>

      {/* Bilingual Content */}
      <div className="space-y-4">
        {/* English Summary */}
        <div className="p-4 bg-medical-dark/30 rounded-lg border-l-4 border-medical-blue">
          <div className="text-sm font-medium text-medical-blue mb-2">
            English Summary
          </div>
          <p className="text-foreground leading-relaxed">
            Your HbA1c is a bit high, meaning your blood sugar has been above
            normal. Start by reducing sugary drinks and walking 30 min daily.
          </p>
        </div>

        {/* Arabic Summary */}
        <div className="p-4 bg-medical-dark/30 rounded-lg border-r-4 border-medical-teal text-right">
          <div className="text-sm font-medium text-medical-teal mb-2">
            الملخص العربي
          </div>
          <p className="text-foreground leading-relaxed" dir="rtl">
            هذا يعني أن نسبة السكر لديك أعلى من الطبيعي قليلاً. ابدأ بتقليل
            المشروبات السكرية والمشي لمدة 30 دقيقة يومياً.
          </p>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="mt-6 flex gap-3">
        <motion.button
          className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-medical-blue hover:bg-medical-blue/80 text-white rounded-lg font-medium transition-colors"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <DocumentArrowDownIcon className="w-4 h-4" />
          Download Arabic PDF
        </motion.button>
        <motion.button
          className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-medical-teal hover:bg-medical-teal/80 text-white rounded-lg font-medium transition-colors"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <DocumentArrowDownIcon className="w-4 h-4" />
          Download Doctor PDF
        </motion.button>
      </div>

      {/* Footer Note */}
      <div className="mt-4 p-3 bg-medical-amber/10 rounded-lg border border-medical-amber/20">
        <p className="text-xs text-medical-amber text-center">
          📋 Always consult your healthcare provider for personalized medical
          advice
        </p>
      </div>
    </motion.div>
  );
};

export default PatientSummary;

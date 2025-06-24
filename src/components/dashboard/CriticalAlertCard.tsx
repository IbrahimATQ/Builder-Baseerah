import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ExclamationTriangleIcon,
  UserPlusIcon,
  EyeIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";

interface CriticalAlertCardProps {
  className?: string;
}

const CriticalAlertCard: React.FC<CriticalAlertCardProps> = ({
  className = "",
}) => {
  const [isVisible, setIsVisible] = useState(true);

  const handleDismiss = () => {
    setIsVisible(false);
  };

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          className={`glass-enhanced rounded-xl border-2 border-medical-red/30 relative overflow-hidden ${className}`}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{
            opacity: 1,
            scale: 1,
            boxShadow: [
              "0 0 0 rgba(239, 68, 68, 0.3)",
              "0 0 20px rgba(239, 68, 68, 0.4)",
              "0 0 0 rgba(239, 68, 68, 0.3)",
            ],
          }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{
            duration: 0.3,
            boxShadow: {
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            },
          }}
        >
          {/* Pulsing border animation */}
          <div className="absolute inset-0 rounded-xl border-2 border-medical-red/50 animate-pulse" />

          {/* Header */}
          <div className="p-4 border-b border-medical-red/20 bg-medical-red/5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-medical-red/20">
                  <ExclamationTriangleIcon className="w-5 h-5 text-medical-red" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-medical-red">
                    🚨 Critical Alert
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Immediate attention required
                  </p>
                </div>
              </div>
              <button
                onClick={handleDismiss}
                className="p-1 rounded-full hover:bg-medical-red/20 transition-colors"
              >
                <XMarkIcon className="w-4 h-4 text-muted-foreground hover:text-medical-red" />
              </button>
            </div>
          </div>

          {/* Alert Content */}
          <div className="p-4">
            <div className="mb-4">
              <h4 className="text-base font-medium text-foreground mb-2">
                Elevated Creatinine
              </h4>
              <p className="text-sm text-muted-foreground">
                Suggest referral to Nephrology for further evaluation and
                management.
              </p>
            </div>

            {/* Alert Details */}
            <div className="grid grid-cols-2 gap-3 mb-4 text-xs">
              <div>
                <span className="text-muted-foreground">Patient ID:</span>
                <span className="text-foreground ml-1 font-mono">#12847</span>
              </div>
              <div>
                <span className="text-muted-foreground">Severity:</span>
                <span className="text-medical-red ml-1 font-medium">High</span>
              </div>
              <div>
                <span className="text-muted-foreground">Value:</span>
                <span className="text-foreground ml-1 font-mono">
                  2.4 mg/dL
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Normal:</span>
                <span className="text-foreground ml-1 font-mono">
                  0.6-1.2 mg/dL
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-2">
              <motion.button
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-medical-red hover:bg-medical-red/80 text-white rounded-lg text-sm font-medium transition-colors"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <UserPlusIcon className="w-4 h-4" />
                Auto-Refer
              </motion.button>
              <motion.button
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-medical-dark/50 hover:bg-medical-dark/70 text-foreground border border-medical-glass-border rounded-lg text-sm font-medium transition-colors"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <EyeIcon className="w-4 h-4" />
                View Details
              </motion.button>
            </div>
          </div>

          {/* Priority Indicator */}
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-medical-red" />

          {/* Timestamp */}
          <div className="px-4 pb-3">
            <p className="text-xs text-muted-foreground">
              Detected {new Date().toLocaleTimeString()} • AI Confidence: 96%
            </p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default CriticalAlertCard;

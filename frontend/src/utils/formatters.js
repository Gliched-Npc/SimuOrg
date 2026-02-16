/**
 * Format a decimal as a percentage string.
 * e.g. 0.156 => "15.6%"
 */
export const toPercent = (value, decimals = 1) => {
    return `${(value * 100).toFixed(decimals)}%`;
};

/**
 * Format a number with commas.
 * e.g. 12345 => "12,345"
 */
export const formatNumber = (num) => {
    return num.toLocaleString();
};

/**
 * Capitalize the first letter of a string.
 */
export const capitalize = (str) => {
    return str.charAt(0).toUpperCase() + str.slice(1);
};

/**
 * Convert snake_case to Title Case.
 * e.g. "high_workload" => "High Workload"
 */
export const snakeToTitle = (str) => {
    return str
        .split('_')
        .map((word) => capitalize(word))
        .join(' ');
};

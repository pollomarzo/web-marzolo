// Format date to a more readable format
export const formatDate = (
    dateString: string,
): { formattedDate: string; formattedTime: string } => {
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) {
            return { formattedDate: "Invalid date", formattedTime: "" };
        }
        const formattedDate = new Intl.DateTimeFormat("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
        }).format(date);

        const formattedTime = new Intl.DateTimeFormat("en-US", {
            hour: "2-digit",
            minute: "2-digit",
            hour12: true,
        }).format(date);

        return { formattedDate, formattedTime };
    } catch (error) {
        console.error("Error formatting date:", error);
        return { formattedDate: "Invalid date", formattedTime: "" };
    }
};
# TerraSign – Real Estate Transfer Platform

## What the project does
TerraSign is a web application designed to manage real estate transfer contracts. It features role-based workflows for different users (Buyer, Seller, Notary, Registry Officer, Admin) and incorporates on-chain verification using the Solana blockchain.

## Technologies used
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS
- **Backend:** Supabase (Auth, PostgreSQL, Edge Functions)
- **Blockchain:** Solana Devnet, Anchor, Phantom Wallet Adapter

## Likely purpose
The project aims to streamline the process of real estate transactions by providing a digital platform that facilitates contract management and verification, enhancing security and efficiency in property transfers.

## Important observations from selected files
- **Role Management:** The application supports multiple user roles, each with specific permissions, ensuring that only authorized users can perform certain actions (e.g., creating cases, signing contracts).
- **Blockchain Integration:** It utilizes Solana for on-chain verification, which adds a layer of security and transparency to the contract process.
- **Environment Configuration:** The setup requires specific environment variables for Supabase integration, indicating a reliance on external services for authentication and data storage.
- **File Structure:** The project is organized into components, context providers, hooks, and pages, promoting modularity and reusability in the codebase.
- **Contract Data Extraction:** The application includes functions for extracting structured data from real estate contracts, indicating a focus on automating and simplifying data handling within the platform.
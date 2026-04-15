import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"GQiX2ORVnYmK","alg":"RS256","n":"0neLCHp0vKjf3RoatM8Km6AKhGyaEr0Eeqh23uPhAReO1OlK","e":"AQAB","p":"GFKdKVierMff3EFz__RxPKNpp1znzSNf6T86LgsqWNdBGEwx","q":"wBp6Zjb2bPtf5ayYXMPAZQTl5KQDRY8kVoIgeeO-QIMfA1WG","dp":"TMhN-U1sIBarT1sVT0Dpl88ZzrvZQJx3lrQnwvZgj7t5mvCO","dq":"T-Vw1LtR_hMU8UeXqRUvukMUmiNUQdapNkHAuXgKtl-ZYc7q"}
const key8 = {"kty":"RSA","kid":"GQiX2ORVnYmK","alg":"RS256","n":"0neLCHp0vKjf3RoatM8Km6AKhGyaEr0Eeqh23uPhAReO1OlK","e":"AQAB","p":"GFKdKVierMff3EFz__RxPKNpp1znzSNf6T86LgsqWNdBGEwx","q":"wBp6Zjb2bPtf5ayYXMPAZQTl5KQDRY8kVoIgeeO-QIMfA1WG","dp":"TMhN-U1sIBarT1sVT0Dpl88ZzrvZQJx3lrQnwvZgj7t5mvCO","dq":"T-Vw1LtR_hMU8UeXqRUvukMUmiNUQdapNkHAuXgKtl-ZYc7q"};
void importJWK(key8, 'RS256');

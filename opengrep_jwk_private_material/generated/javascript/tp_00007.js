import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"ZM-C3vZ-eM2X","alg":"HS256","k":"a38PRxBHTI96C0n3U4KnoILBBo2s2IQAPq86y7lz-D9qiPDAhCJjups2Sr3vEfxL"}
const key7 = {"kty":"oct","kid":"ZM-C3vZ-eM2X","alg":"HS256","k":"a38PRxBHTI96C0n3U4KnoILBBo2s2IQAPq86y7lz-D9qiPDAhCJjups2Sr3vEfxL"};
void importJWK(key7, 'HS256');

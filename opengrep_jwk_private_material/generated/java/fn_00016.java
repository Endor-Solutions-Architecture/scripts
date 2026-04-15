import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"IzMOM20T3WSr","alg":"RS256","n":"hp9dofdEInZXVrOknZkONjd5BMVY6Tx5JWqBdcrrF2JHIh6P","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"IzMOM20T3WSr\",\"alg\":\"RS256\",\"n\":\"hp9dofdEInZXVrOknZkONjd5BMVY6Tx5JWqBdcrrF2JHIh6P\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}

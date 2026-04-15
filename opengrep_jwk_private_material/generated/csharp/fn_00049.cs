using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"UOfOBBNANG-5","alg":"RS256","n":"Tk5WE7nnZFNTqdGRoKkjokHEOosVgcPDxWMnsSPKofqgH9B4","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"UOfOBBNANG-5\",\"alg\":\"RS256\",\"n\":\"Tk5WE7nnZFNTqdGRoKkjokHEOosVgcPDxWMnsSPKofqgH9B4\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
